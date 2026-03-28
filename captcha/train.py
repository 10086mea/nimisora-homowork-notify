# 文件名: train.py

import os
import random
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, ConcatDataset, Subset
from torchvision import transforms
from PIL import Image
from tqdm import tqdm
from torch.optim.lr_scheduler import ReduceLROnPlateau

from .model import CaptchaCNN

# --- 配置 ---
SYNTHETIC_TRAIN_DIR = 'dataset/train'
REAL_DATA_DIR = 'data/correct_captchas'
MODEL_SAVE_DIR = 'runs'
# 改为保存检查点文件，包含 model+optimizer+epoch+best_val_acc
MODEL_CHECKPOINT_PATH = os.path.join(MODEL_SAVE_DIR, 'multi_head_cnn_checkpoint.pth')
MODEL_SAVE_PATH = os.path.join(MODEL_SAVE_DIR, 'multi_head_cnn_best.pth')

# --- 训练参数 ---
EPOCHS = 40
BATCH_SIZE = 64
LEARNING_RATE = 1e-4

# 验证码字符集
CHAR_SET = '0123456789'
NUM_CLASSES = len(CHAR_SET)
NUM_CHARS = 4

char_to_id = {char: i for i, char in enumerate(CHAR_SET)}
id_to_char = {i: char for i, char in enumerate(CHAR_SET)}

# --- 数据集类 ---
class SyntheticCaptchaDataset(Dataset):
    """加载合成验证码数据。"""
    def __init__(self, data_dir):
        self.data_dir = data_dir
        all_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith('.png')]
        # 仅保留文件名前缀长度为 NUM_CHARS 且全部在 CHAR_SET 中的图片，避免后续递归/异常
        def _valid(p: str) -> bool:
            prefix = os.path.basename(p).split('_')[0]
            return len(prefix) == NUM_CHARS and all(ch in CHAR_SET for ch in prefix)
        self.image_paths = [p for p in all_paths if _valid(p)]
        self.transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5])
        ])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        image_path = self.image_paths[idx]
        label_text = os.path.basename(image_path).split('_')[0]
        label_ids = [char_to_id[char] for char in label_text]
        label_tensor = torch.tensor(label_ids, dtype=torch.long)
        image = Image.open(image_path)
        image = self.transform(image)
        return image, label_tensor

class RealCaptchaDataset(Dataset):
    """加载真实的、已标注的验证码数据。"""
    def __init__(self, data_dir):
        self.data_dir = data_dir
        all_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith('.png')]
        # 实际文件名形如 6216_1759934033062.png，取下划线前缀作为标签
        def _valid(p: str) -> bool:
            prefix = os.path.basename(p).split('_')[0]
            return len(prefix) == NUM_CHARS and all(ch in CHAR_SET for ch in prefix)
        self.image_paths = [p for p in all_paths if _valid(p)]
        self.transform = transforms.Compose([
            transforms.Resize((26, 80)),
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5])
        ])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        image_path = self.image_paths[idx]
        # 只取下划线前的四位作为标签，避免把时间戳算进去
        label_text = os.path.basename(image_path).split('_')[0]
        label_ids = [char_to_id[char] for char in label_text]
        label_tensor = torch.tensor(label_ids, dtype=torch.long)
        image = Image.open(image_path)
        image = self.transform(image)
        return image, label_tensor

# --- 主训练流程 ---
def main(resume: bool = True):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

    # --- 核心修改: 严格分离训练集和验证集 ---
    synthetic_dataset = SyntheticCaptchaDataset(SYNTHETIC_TRAIN_DIR)
    
    if not os.path.exists(REAL_DATA_DIR) or not os.listdir(REAL_DATA_DIR):
        print(f"警告: 真实数据目录 '{REAL_DATA_DIR}' 不存在或为空。将只使用合成数据进行训练和验证（按比例拆分）。")
        # 当没有真实数据时，从合成数据中按 90/10 划分训练/验证
        dataset_size = len(synthetic_dataset)
        indices = list(range(dataset_size))
        split = int(dataset_size * 0.9)
        random.shuffle(indices)
        train_indices, val_indices = indices[:split], indices[split:]
        train_dataset = Subset(synthetic_dataset, train_indices)
        val_dataset = Subset(synthetic_dataset, val_indices)
    else:
        real_dataset = RealCaptchaDataset(REAL_DATA_DIR)
        
        # 随机打乱真实数据集的索引
        dataset_size = len(real_dataset)
        indices = list(range(dataset_size))
        split = int(dataset_size * 0.8) # 80% 训练, 20% 验证
        random.shuffle(indices)
        train_indices, val_indices = indices[:split], indices[split:]

        # 创建真实数据的训练子集和验证子集
        real_train_subset = Subset(real_dataset, train_indices)
        real_val_subset = Subset(real_dataset, val_indices)

        # 最终的训练集 = 合成数据 + 80%的真实数据
        # train_dataset = ConcatDataset([synthetic_dataset, real_train_subset])
        train_dataset = real_train_subset
        # 最终的验证集 = 20%的真实数据
        val_dataset = real_val_subset
        
        print(f"训练集: {len(synthetic_dataset)} 合成图片 + {len(real_train_subset)} 真实图片 = {len(train_dataset)} 总图片")
        print(f"验证集: {len(real_val_subset)} 张真实图片 (从真实数据集中分离)")

    # 在 Windows 上将 num_workers 降低为 0 可避免 fork 问题；如果可用可改成 4
    num_workers = 0
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=num_workers, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=num_workers)
    
    model = CaptchaCNN(num_chars=NUM_CHARS, num_classes=NUM_CLASSES, in_channels=1).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)
    scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.2, patience=3, verbose=True)
    
    best_val_acc = 0.0
    start_epoch = 0

    # 如果需要从检查点恢复训练，尝试加载检查点（包含 optimizer 状态）
    if resume and os.path.exists(MODEL_CHECKPOINT_PATH):
        try:
            print(f"找到检查点 {MODEL_CHECKPOINT_PATH}，尝试加载...")
            ckpt = torch.load(MODEL_CHECKPOINT_PATH, map_location=device)
            # 兼容两种格式：checkpoint 包含 keys，或直接是 state_dict
            if isinstance(ckpt, dict) and 'model_state_dict' in ckpt:
                model.load_state_dict(ckpt['model_state_dict'])
                if 'optimizer_state_dict' in ckpt:
                    optimizer.load_state_dict(ckpt['optimizer_state_dict'])
                start_epoch = ckpt.get('epoch', 0) + 1
                best_val_acc = ckpt.get('best_val_acc', 0.0)
                print(f"已从检查点恢复，start_epoch={start_epoch}, best_val_acc={best_val_acc}")
            else:
                # 旧格式：仅保存了模型权重
                model.load_state_dict(ckpt)
                start_epoch = 0
                print("检查点为旧格式（仅权重），已加载模型参数，优化器与 epoch 从头开始。")
        except Exception as e:
            print(f"加载检查点失败: {e}，将从头开始训练。")

    for epoch in range(start_epoch, EPOCHS):
        model.train()
        train_loss = 0
        pbar_train = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS} [训练]")
        for images, labels in pbar_train:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            labels = labels.permute(1, 0)
            loss = sum(criterion(outputs[i], labels[i]) for i in range(NUM_CHARS))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            pbar_train.set_postfix(loss=f'{loss.item() / NUM_CHARS:.4f}')
        
        print(f"Epoch {epoch+1}/{EPOCHS}, 训练损失: {train_loss / len(train_loader):.4f}")
        
        model.eval()
        val_correct, val_total = 0, 0
        pbar_val = tqdm(val_loader, desc=f"Epoch {epoch+1}/{EPOCHS} [验证]")
        with torch.no_grad():
            for images, labels in pbar_val:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                outputs = torch.stack(outputs, dim=0).permute(1, 0, 2)
                preds = outputs.argmax(dim=2)
                val_correct += torch.all(preds == labels, dim=1).sum().item()
                val_total += images.size(0)
                        
        val_acc = val_correct / val_total if val_total > 0 else 0
        print(f"Epoch {epoch+1}/{EPOCHS}, 真实数据验证准确率: {val_acc:.4f}")
        
        scheduler.step(val_acc)
        
        # 每轮保存检查点（包含 optimizer 状态），并在验证最佳时保存单独的最佳模型权重
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'best_val_acc': best_val_acc,
        }
        torch.save(checkpoint, MODEL_CHECKPOINT_PATH)
        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            # 也更新检查点中的 best_val_acc
            checkpoint['best_val_acc'] = best_val_acc
            torch.save(checkpoint, MODEL_CHECKPOINT_PATH)
            print(f"模型已保存，当前最佳真实数据准确率: {best_val_acc:.4f}")

if __name__ == '__main__':
    main()
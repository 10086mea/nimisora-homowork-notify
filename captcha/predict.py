# captcha/predict.py

import torch
from PIL import Image
from torchvision import transforms
import os

# 1. 导入正确的模型类
from .model import CaptchaCNN
# 2. 从新的训练脚本中导入必要的变量
from .train import NUM_CHARS, NUM_CLASSES, id_to_char

# 4. 使用和 train.py 完全一致的图像预处理
transform = transforms.Compose([
    transforms.Resize((26, 80)),
    transforms.Grayscale(num_output_channels=1),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5], std=[0.5])
])

def predict_from_image(model, image: Image.Image):
    """
    对Pillow Image对象进行预测。
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    image = transform(image)
    image = image.unsqueeze(0) # 增加batch维度 -> (1, 1, 26, 80)
    image = image.to(device)

    predicted_text = ""
    with torch.no_grad():
        outputs = model(image) # 模型输出是一个包含4个张量的列表

        # 将输出列表堆叠成一个张量: (4, batch_size=1, 10)
        outputs = torch.stack(outputs, dim=0)
        # 交换维度以匹配我们需要的格式: (batch_size=1, 4, 10)
        outputs = outputs.permute(1, 0, 2)

        # 找到每个位置概率最高的预测索引
        preds_indices = outputs.argmax(dim=2) # 形状: (1, 4)

        # 将索引转换为字符
        char_list = [id_to_char[idx.item()] for idx in preds_indices.squeeze()]
        predicted_text = "".join(char_list)

    return predicted_text

def load_model(model_path):
    """
    加载多头CNN模型。
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 3. 实例化新的 CaptchaCNN 模型
    model = CaptchaCNN(num_chars=NUM_CHARS, num_classes=NUM_CLASSES, in_channels=1)
    try:
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    except FileNotFoundError:
        print(f"错误: 找不到模型文件 '{model_path}'。请先运行 train.py 进行训练。")
        return None
    return model

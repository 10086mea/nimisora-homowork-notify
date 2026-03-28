# 文件名: model.py

import torch
import torch.nn as nn

class CaptchaCNN(nn.Module):
    """
    一个专门用于识别固定长度（如4位）验证码的纯CNN模型。
    它包含一个共享的CNN主干和多个独立的分类头。
    """
    def __init__(self, num_chars=4, num_classes=10, in_channels=1):
        """
        初始化模型。
        :param num_chars: 验证码的字符数量，即头的数量。
        :param num_classes: 每个字符的类别数（例如0-9有10类）。
        :param in_channels: 输入图像的通道数（1代表灰度图，3代表彩色图）。
        """
        super(CaptchaCNN, self).__init__()
        self.num_chars = num_chars
        
        # --- 共享的CNN主干 ---
        # 这个结构会产生 256 * 1 * 5 = 1280 个特征
        self.cnn_backbone = nn.Sequential(
            # 输入: (batch, 1, 26, 80)
            nn.Conv2d(in_channels, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d(kernel_size=2, stride=2), # -> (batch, 32, 13, 40)

            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d(kernel_size=2, stride=2), # -> (batch, 64, 6, 20)

            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d(kernel_size=2, stride=2), # -> (batch, 128, 3, 10)
            
            nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.MaxPool2d(kernel_size=2, stride=2), # -> (batch, 256, 1, 5)
        )
        
        # --- 动态计算CNN输出尺寸 ---
        with torch.no_grad():
            dummy_input = torch.zeros(1, in_channels, 26, 80)
            cnn_out = self.cnn_backbone(dummy_input)
            self.flattened_size = cnn_out.view(1, -1).size(1)
            
        # --- 四个独立的分类头 ---
        self.heads = nn.ModuleList([
            nn.Linear(self.flattened_size, num_classes) for _ in range(num_chars)
        ])

        # 添加 Dropout 层用于正则化
        self.dropout = nn.Dropout(p=0.5)

    def forward(self, x):
        features = self.cnn_backbone(x)
        features = features.view(features.size(0), -1)
        
        # 在全连接层之前应用 Dropout
        # 注意: dropout 在 model.eval() 模式下会自动禁用
        features = self.dropout(features)
        
        outputs = [head(features) for head in self.heads]
        return outputs
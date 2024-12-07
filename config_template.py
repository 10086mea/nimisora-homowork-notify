# config_template.py

# SMTP 配置
SMTP_SERVER = "smtp.qq.com"  # SMTP 服务器地址
SMTP_PORT = 465  # SMTP 服务器端口
SMTP_USER = "your_email@qq.com"  # 你的邮箱地址
SMTP_PASSWORD = "your_smtp_password"  # 你的 SMTP 密码
CSV_FILE_PATH = 'user_data.csv'  # CSV文件路径
log_file_path = '.\\homeworks'  # log文件路径
SECRET_KEY = "一般密码不填错就用不上(?而且需要配合订阅前端使用" # 用于发送修改订阅密码邮件时生成token的AES密钥
DEFAULT_PASSWORD_PREFIX = "应反馈，为了防止有人干坏事，这个，就先不往这里写了" # 智慧平台默认密码学号前面的前缀
# 应用程序配置
MAX_REMIND_COUNT = 1  # 最多提醒次数
KAWAII_IMAGE = "path/to/your/image.png"  # 右下角的二刺螈图片文件路径，例: "D:\\path\\to\\image.png"
QAQ_IMAGE="path/to/your/image.png" # 修改订阅密码邮件的二次元图片

# Web 服务的基本 URL
BASE_URL = "http://123.121.147.7:88/ve"

# 其他与 SMTP 相关的配置
MAIL_SMTP_MODE = "smtp"  # 邮件发送模式，使用 SMTP
MAIL_SENDMAIL_MODE = "smtp"  # 邮件发送方式，使用 SMTP
MAIL_FROM_ADDRESS = "your_email_id"  # 发件人信息，qq邮箱写q号就行
MAIL_DOMAIN = "qq.com"  # 邮件域名
MAIL_SMTP_AUTH = True  # 是否启用 SMTP 认证
MAIL_SMTP_SECURE = "ssl"  # SMTP 加密方式，使用 SSL


# config.py

# SMTP 配置
SMTP_SERVER = "smtp.qq.com"  # SMTP 服务器地址
SMTP_PORT = 465  # SMTP 服务器端口
SMTP_USER = "3239799381@qq.com"  # 你的邮箱地址
SMTP_PASSWORD = "jhwqboizpaxgcjba"  # 你的 SMTP 密码

# 应用程序配置
REMINDER_TIME_THRESHOLD = 96  # 提醒时间阈值（以小时为单位）
MAX_REMIND_COUNT = 1  # 最多提醒次数
KAWAII_IMAGE="D:\\react\Apache24\wordpress\\bgimages\sora.png"
# Web 服务的基本 URL
BASE_URL = "http://123.121.147.7:88/ve"

# 其他与 SMTP 相关的配置
MAIL_SMTP_MODE = "smtp"  # 邮件发送模式，使用 SMTP
MAIL_SENDMAIL_MODE = "smtp"  # 邮件发送方式，使用 SMTP
MAIL_FROM_ADDRESS = "3239799381"  # 发件人地址
MAIL_DOMAIN = "qq.com"  # 邮件域名
MAIL_SMTP_AUTH = True  # 是否启用 SMTP 认证
MAIL_SMTP_SECURE = "ssl"  # SMTP 加密方式，使用 SSL

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from datetime import datetime, timedelta
from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, KAWAII_IMAGE
import base64
import json
import csv

def select_remind_homework(homework_data_json, to_email, reminder_threshold_hours, last_notified, csv_file_path,
                           student_id):
    """
    检查作业数据并根据提醒阈值条件筛选出需要提醒的作业项，并保存到CSV文件。

    :param homework_data_json: JSON格式的所有课程作业数据
    :param to_email: 用户邮箱，用于发送提醒
    :param reminder_threshold_hours: 提前多少小时提醒的阈值列表（第一个值为普通提醒阈值，第二个值为紧急提醒阈值）
    :param last_notified: 上次通知时间，格式为 "%Y-%m-%d %H:%M:%S"
    :param csv_file_path: 用于保存提醒内容的CSV文件路径
    :param student_id: 学生学号，用于根据学号保存不同的CSV文件
    """
    current_time = datetime.now()
    email_reminders = {"normal": [], "urgent": [], "out_of_threshold": []}  # 新增 "out_of_threshold" 类别

    # 将字符串形式的上次通知时间转换为 datetime 对象
    last_notified_time = last_notified

    # 将JSON格式的作业数据解析为Python对象
    all_courses_homework_data = json.loads(homework_data_json)

    # 遍历所有课程的作业
    for course_name, homeworks in all_courses_homework_data.items():
        for homework_info in homeworks:
            end_time_str = homework_info.get("结束时间")
            try:
                end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S") if end_time_str else None
                # 如果结束时间为0点0分0秒，将其调整为前一天晚上23点59分59秒
                if end_time and end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0:
                    end_time -= timedelta(seconds=1)
                    # 将调整后的时间重新格式化为字符串并更新到原始数据
                    homework_info["结束时间"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M") if end_time_str else None
                # 再次检查0点0分的情况
                if end_time and end_time.hour == 0 and end_time.minute == 0:
                    end_time -= timedelta(seconds=1)
                    # 将调整后的时间重新格式化为字符串并更新到原始数据
                    homework_info["结束时间"] = end_time.strftime("%Y-%m-%d %H:%M")

            # 检查作业是否未提交
            if homework_info["提交状态"] == "未提交" and end_time:
                time_remaining = (end_time - current_time).total_seconds()  # 剩余时间，单位为秒
                # 根据时间阈值分类提醒类型
                if time_remaining >= 0:  # 确保剩余时间为非负数
                    if time_remaining < reminder_threshold_hours[1] * 3600:  # 紧急提醒
                        email_reminders["urgent"].append((course_name, homework_info))
                    elif time_remaining < reminder_threshold_hours[0] * 3600:  # 普通提醒
                        email_reminders["normal"].append((course_name, homework_info))
                    else:  # 超出阈值作业
                        email_reminders["out_of_threshold"].append((course_name, homework_info))
                else:
                    print(f"{course_name} 作业已超过提交时间，未添加提醒")

    # 获取上次的提醒内容
    last_reminders = load_last_reminders(student_id, csv_file_path)

    # 判断当前提醒内容与上次是否相同
    if not compare_reminders(email_reminders, last_reminders):
        # 保存新提醒内容到 CSV 文件
        save_reminders_to_csv(email_reminders, csv_file_path, student_id)

        send_summary_email(email_reminders, to_email)
        print("紧急程度或普通提醒有变化，需要提醒")
        return email_reminders  # 返回提醒内容
    else:
        #没变化也要保存
        save_reminders_to_csv(email_reminders, csv_file_path, student_id)
        print("提醒内容没有变化")
        return None  # 无需提醒



def compare_reminders(current_reminders, last_reminders):
    """
    比较当前提醒内容和上次提醒内容，仅比较关键字段。
    :param current_reminders: 当前生成的提醒内容
    :param last_reminders: 上次保存的提醒内容
    :return: 布尔值，表示是否相同
    """
    for reminder_type in ["urgent", "normal"]: # 忽略掉阈值外的作业
        current_set = {
            (course_name, info.get("作业标题") or info.get("作业名称"), info.get("结束时间"), info.get("提交状态"))
            for course_name, info in current_reminders[reminder_type]
        }
        last_set = {
            (course_name, info.get("作业标题") or info.get("作业名称"), info.get("结束时间"), info.get("提交状态"))
            for course_name, info in last_reminders[reminder_type]
        }

        if current_set != last_set:
            return False
    return True

def save_reminders_to_csv(email_reminders, csv_file_path, student_id):
    """
    将提醒内容保存到 CSV 文件中。

    :param email_reminders: 包含 "urgent" 和 "normal" 作业的字典
    :param csv_file_path: CSV 文件的保存路径
    :param student_id: 学生学号，用于根据学号保存不同的CSV文件
    """
    fieldnames = ["课程名称", "作业标题", "结束时间", "提交状态", "提醒类型"]

    # 打开 CSV 文件并写入数据
    with open(f"{student_id}_{csv_file_path}", mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        # 写入表头
        writer.writeheader()

        # 将 urgent 和 normal 列表的数据写入 CSV
        for reminder_type in ["urgent", "normal","out_of_threshold"]:
            for course_name, homework_info in email_reminders[reminder_type]:
                reminder_data = {
                    "课程名称": course_name,
                    "作业标题": homework_info.get("作业标题", ""),
                    "结束时间": homework_info.get("结束时间", ""),
                    "提交状态": homework_info.get("提交状态", ""),
                    "提醒类型": reminder_type
                }
                writer.writerow(reminder_data)


def load_last_reminders(student_id, csv_file_path):
    """
    从 CSV 文件加载上次的提醒内容。

    :param student_id: 学生学号，用于根据学号加载对应的CSV文件
    :param csv_file_path: CSV 文件的保存路径
    :return: 上次提醒的内容，格式为 {"normal": [], "urgent": []}
    """
    reminders = {"normal": [], "urgent": [],"out_of_threshold":[]}
    try:
        with open(f"{student_id}_{csv_file_path}", mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                reminder_type = row["提醒类型"]
                reminders[reminder_type].append((row["课程名称"], {
                    "作业标题": row["作业标题"],
                    "结束时间": row["结束时间"],
                    "提交状态": row["提交状态"]
                }))
    except FileNotFoundError:
        # 如果文件不存在，则返回空提醒内容
        pass
    return reminders

def send_summary_email(email_reminders, to_email):
    """
    发送电子邮件汇总给用户。
    """
    subject = "[新海天提醒] 即将到期的作业汇总"

    # 将图片文件读取为 Base64 编码字符串
    with open(KAWAII_IMAGE, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    # HTML 邮件内容
    body = f"""
    <html>
    <head>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background-color: #fafafa;
          color: #333;
        }}
        .container {{
          max-width: 600px;
          margin: 20px auto;
          padding: 20px;
          background-color: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
          position: relative; /* 使内部图片相对于 container 定位 */
        }}
        .header {{
          text-align: center;
          margin-bottom: 20px;
        }}
        .header h2 {{
          color: #4a90e2;
          font-weight: bold;
        }}
        .content {{
          margin-top: 20px;
          line-height: 1.6;
        }}
        .course {{
          margin-bottom: 15px;
          padding: 10px;
          border-left: 4px solid #4a90e2;
          background-color: #f9f9f9;
          border-radius: 5px;
        }}
        .urgent-course {{
          margin-bottom: 15px;
          padding: 10px;
          border-left: 4px solid red;
          background-color: #ffe6e6;
          border-radius: 5px;
          color: red;
        }}
        .out_of_threshold-course {{
        margin-bottom: 15px;
        padding: 10px;
        border-left: 4px solid #b0b0b0; /* 灰色的左边框 */
        background-color: #f2f2f2;      /* 浅灰色背景 */
        border-radius: 5px;
        color: #808080;                 /* 灰色字体 */
        }}

        .footer {{
          text-align: center;
          font-size: 0.9em;
          color: #888;
          margin-top: 20px;
        }}
        .chibi-img {{
          position: absolute;
          bottom: 5%; /* 距离 container 底部的距离 */
          right: 5%; /* 距离 container 右侧的距离 */
          max-width: 24%; /* 控制缩放比例 */
          height: auto;
          opacity: 0.85;
        }}
            /* 移动设备样式 */
        @media (max-width: 600px) {{
          .container {{
            width: 100%;
            padding: 10px;
            border-radius: 0; /* 在移动端去掉圆角以适应屏幕 */
          }}
          .chibi-img {{
            max-width: 8%; /* 移动端缩小图片比例 */
          }}
          .header h2 {{
            font-size: 1.5em;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h2>即将到期的作业提醒</h2>
        </div>
        <div class="content">
          <p>欧哈呦！</p>
          <p>尼尼有下列课程的作业即将到期：</p>
    """

    # 紧急提醒内容
    if email_reminders["urgent"]:
        body += "<h3 style='color: red;'>紧急提醒：</h3>"
        for course_name, homework_info in email_reminders["urgent"]:
            body += f"""
              <div class="urgent-course">
                <strong>课程：</strong> {course_name}<br>
                <strong>作业标题：</strong> {homework_info['作业标题']}<br>
                <strong>截止时间：</strong> {homework_info['结束时间']}<br>
              </div>
            """

    # 普通提醒内容
    if email_reminders["normal"]:
        body += "<h3>普通提醒：</h3>"
        for course_name, homework_info in email_reminders["normal"]:
            body += f"""
              <div class="course">
                <strong>课程：</strong> {course_name}<br>
                <strong>作业标题：</strong> {homework_info['作业标题']}<br>
                <strong>截止时间：</strong> {homework_info['结束时间']}<br>
              </div>
            """
    # 普通提醒内容
    if email_reminders["out_of_threshold"]:
        body += "<h3>还早的很的作业：</h3>"
        for course_name, homework_info in email_reminders["out_of_threshold"]:
            body += f"""
              <div class="out_of_threshold-course">
                <strong>课程：</strong> {course_name}<br>
                <strong>作业标题：</strong> {homework_info['作业标题']}<br>
                <strong>截止时间：</strong> {homework_info['结束时间']}<br>
              </div>
            """

    body += f"""
        
          <p>不要忘了交作业哦~</p>
          <br><br> <!-- 额外空行 -->
          <br><br> <!-- 额外空行 -->
          <br><br> <!-- 额外空行 -->
        </div>
        <div class="footer">
        </div>
        <img src="data:image/png;base64,{encoded_string}" alt="Q版人物图像" class="chibi-img">
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    print(f"正在发送给 {to_email} 的提醒邮件...")
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"成功发送提醒邮件给 {to_email}")
    except Exception as e:
        # 检查异常内容，如果是特定错误则忽略
        if str(e) == "(-1, b'\\x00\\x00\\x00')":
            print(f"成功发送提醒邮件给 {to_email}，但收到非标准响应。")
        else:
            print(f"发送邮件失败：{e}")
import csv
import schedule
import time
from config import BASE_URL
from datetime import datetime
from session_management import initialize_session, get_captcha, perform_login
from data_fetch import fetch_semester_info, fetch_user_info, fetch_course_list, fetch_homework_data
from email_util import select_remind_homework

CSV_FILE_PATH = 'user_data.csv'  # CSV文件路径
csv_file_path = 'class_log.csv'

def load_users_from_csv(file_path):
    """从CSV文件加载用户信息，读取学号、邮箱、上次提醒时间和提醒阈值。"""
    users = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            users.append({
                "student_id": row["student_id"],
                "email": row["email"],
                "last_notified": datetime.strptime(row["last_notified"], "%Y-%m-%d %H:%M:%S") if row[
                    "last_notified"] else None,
                "reminder_thresholds": [int(row["reminder_threshold_1"]), int(row["reminder_threshold_2"])]
            })
    return users


def save_users_to_csv(file_path, users):
    """将更新后的用户信息保存到CSV文件中，包含学号、邮箱、上次提醒时间和提醒阈值。"""
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ["student_id", "email", "last_notified", "reminder_threshold_1", "reminder_threshold_2"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for user in users:
            writer.writerow({
                "student_id": user["student_id"],
                "email": user["email"],
                "last_notified": user["last_notified"].strftime("%Y-%m-%d %H:%M:%S") if user["last_notified"] else "",
                "reminder_threshold_1": user["reminder_thresholds"][0],
                "reminder_threshold_2": user["reminder_thresholds"][1]
            })


def login_and_fetch_data(base_url, student_id):
    """主流程：初始化会话，登录并获取数据。"""
    session, jsessionid = initialize_session(base_url)
    captcha = get_captcha(session, base_url)
    perform_login(session, base_url, student_id, jsessionid, captcha)
    semester_info = fetch_semester_info(session, base_url, jsessionid)
    user_info = fetch_user_info(session, base_url, jsessionid)
    course_list = fetch_course_list(session, base_url, jsessionid, semester_info["学期代码"])
    return session, user_info, course_list


def check_and_send_reminders():
    """检查并根据提醒阈值发送提醒邮件。"""
    users = load_users_from_csv(CSV_FILE_PATH)
    current_time = datetime.now()

    for user in users:
        student_id = user["student_id"]
        to_email = user["email"]
        reminder_thresholds = user["reminder_thresholds"]
        last_notified = user["last_notified"]

        # 执行数据抓取和提醒逻辑
        session, user_info, course_list = login_and_fetch_data(BASE_URL, student_id)
        homework_data_json = fetch_homework_data(
            session,
            BASE_URL,
            course_list,
            user_info,
        )
        select_remind_homework(homework_data_json, to_email, reminder_thresholds, last_notified,csv_file_path,student_id)

        # 更新提醒时间为当前时间
        user["last_notified"] = current_time
        print(f"Processed homework data for student {student_id} with threshold {reminder_thresholds}")

    # 保存更新后的用户信息到CSV
    save_users_to_csv(CSV_FILE_PATH, users)


# 启动时立即执行一次检查
check_and_send_reminders()

# 设置定时任务每隔15分钟执行一次
schedule.every(15).minutes.do(check_and_send_reminders)

if __name__ == "__main__":
    print("定时任务启动，启动时立即检查一次，之后每隔15分钟检查一次...")
    while True:
        schedule.run_pending()
        time.sleep(1)

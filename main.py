import csv
import schedule
import time
from config import BASE_URL
from datetime import datetime
from session_management import initialize_session, get_captcha, perform_login, PasswordError
from data_fetch import fetch_semester_info, fetch_user_info, fetch_course_list, fetch_homework_data
from email_util import select_remind_homework, send_password_change_mail
import asyncio
from config import CSV_FILE_PATH, log_file_path
import traceback
from termcolor import colored

def load_users_from_csv(file_path):
    """从CSV文件加载用户信息，读取学号、邮箱、上次提醒时间和提醒阈值。"""
    users = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                users.append({
                    "student_id": row["student_id"],
                    "email": row["email"],
                    "last_notified": datetime.strptime(row["last_notified"], "%Y-%m-%d %H:%M:%S") if row[
                        "last_notified"] else None,
                    "reminder_thresholds": [int(row["reminder_threshold_1"]), int(row["reminder_threshold_2"])],
                    "password": row["password_md5"],
                    "confirmed": int(row["password_confirmed"]),
                    "notified": int(row["password_notified"])
                })
    except PermissionError:
        print(colored("错误：无法访问CSV文件，文件可能被其他程序占用", 'red'))
        raise Exception("CSV文件访问被拒绝，请检查文件是否被其他程序打开")
    except FileNotFoundError:
        print(colored("错误：找不到CSV文件", 'red'))
        raise Exception(f"找不到CSV文件: {file_path}")
    except Exception as e:
        print(colored(f"读取CSV文件时发生错误: {str(e)}", 'red'))
        raise

    if not users:
        print(colored("警告：CSV文件为空或没有有效数据", 'yellow'))
        raise Exception("CSV文件中没有找到任何用户数据")

    print(f"成功从CSV加载了 {len(users)} 个用户")
    return users


def save_users_to_csv(file_path, users):
    """将更新后的用户信息保存到CSV文件中，包含学号、邮箱、上次提醒时间和提醒阈值。"""
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ["student_id", "email", "last_notified", "reminder_threshold_1", "reminder_threshold_2", "password_md5", "password_confirmed", "password_notified"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for user in users:
            writer.writerow({
                "student_id": user["student_id"],
                "email": user["email"],
                "last_notified": user["last_notified"].strftime("%Y-%m-%d %H:%M:%S") if user["last_notified"] else "",
                "reminder_threshold_1": user["reminder_thresholds"][0],
                "reminder_threshold_2": user["reminder_thresholds"][1],
                "password_md5": user["password"],
                "password_confirmed": user["confirmed"],
                "password_notified": user["notified"]
            })


def login_and_fetch_data(base_url, student_id, user):
    """主流程：初始化会话，登录并获取数据。"""
    session, jsessionid = initialize_session(base_url)
    captcha = get_captcha(session, base_url)
    perform_login(session, base_url, student_id, jsessionid, captcha, user) # 若密码错误，不在这处理，而是再向上一级的函数



    semester_info = fetch_semester_info(session, base_url, jsessionid)
    user_info = fetch_user_info(session, base_url, jsessionid)
    course_list = fetch_course_list(session, base_url, jsessionid, semester_info["学期代码"])
    return session, user_info, course_list

async def fetch_and_process_user(user, log_file_path):
    """处理单个用户的数据抓取和提醒逻辑"""
    student_id = user["student_id"]
    to_email = user["email"]
    reminder_thresholds = user["reminder_thresholds"]
    last_notified = user["last_notified"]
    # 执行数据抓取和提醒逻辑
    try:
        session, user_info, course_list = login_and_fetch_data(BASE_URL, student_id, user)
    except PasswordError as e:
        print(f"【登录中抛出账号密码相关错误】：{e}")
        raise #继续向上抛出
    homework_data_json = await fetch_homework_data(
        session,
        BASE_URL,
        course_list,
        user_info,
    )
    select_remind_homework(homework_data_json, to_email, reminder_thresholds, last_notified,
                           log_file_path, student_id)
    return student_id, reminder_thresholds


async def check_and_send_reminders():
    """检查并根据提醒阈值发送提醒邮件。"""
    users = load_users_from_csv(CSV_FILE_PATH)
    current_time = datetime.now()

    for user in users:
        student_id = user["student_id"]
        try:
            if user["confirmed"] == -1:
                print(f"{student_id}的密码不正确，已跳过")
                continue
            student_id, reminder_thresholds = await fetch_and_process_user(user, log_file_path)
            user["last_notified"] = current_time
            print(f" {student_id}学生 阈值 {reminder_thresholds} 处理完毕")
        except PasswordError:
            print(f"{student_id}密码不太对吧")
            if user["notified"] == 0:
                print("好像从没提醒过，那就发个提醒邮件吧")
                send_password_change_mail(student_id, user)
                user["notified"] = 1 # 标记为提醒过
            elif user["notified"] == 1:
                print("提醒过了，那就不管了~")
            continue
        except Exception as e:
            error_trace = traceback.format_exc()
            with open('error.log', 'a') as f:
                f.write(f"{current_time}: Error processing user {user.get('student_id', 'unknown')}:\n{error_trace}\n")
            print(colored(f"处理中发生错误，学号： {user.get('student_id', 'unknown')}:", 'red', attrs=['bold']))
            print(colored(f"Error: {str(e)}", 'red'))
            print(colored(f"Location:\n{error_trace}", 'yellow'))
            continue
    # 保存更新后的用户信息到CSV
    save_users_to_csv(CSV_FILE_PATH, users)

def run_async_check():
    try:
        asyncio.run(check_and_send_reminders())
    except Exception as e:
        print(f"运行异步函数时发生错误: {e}")

if __name__ == "__main__":
    while True:
        try:
            # 启动时立即执行一次检查
            run_async_check()

            # 设置定时任务
            schedule.every(15).minutes.do(run_async_check)

            print("定时任务启动，启动时立即检查一次，之后每隔15分钟检查一次...")
            while True:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            print(f"主循环发生错误: {e}")
            time.sleep(5)  # 发生错误后等待5秒再重试

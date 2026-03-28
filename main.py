# main.py

import time
from sqlalchemy.orm import Session
import asyncio
from datetime import datetime, timedelta
import argparse
import threading
from collections import deque

from database import init_db, get_db
from services import user_service, main_service, homework_service, notification_service
from models import User, Homework

crawl_queue = deque()

def crawl_user_data(user_id: int):
    """The core crawl function. Only fetches and updates data."""
    db: Session = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"[爬虫] 任务失败：找不到用户ID {user_id}。")
            return

        print(f"[爬虫] 开始为用户 {user.student_id} 爬取数据...")
        session, jsessionid, session_id = main_service.login(db, user)
        semester_info = main_service.fetch_semester_info(session, jsessionid)
        course_list = main_service.fetch_course_list(session, jsessionid, semester_info['xqCode'], session_id)
        homework_data = asyncio.run(main_service.fetch_all_homework_data(session, course_list, session_id, jsessionid))

        for course_name, homeworks in homework_data.items():
            for hw_data in homeworks:
                end_time_str = hw_data.get('end_time')
                if not end_time_str:
                    print(f"[警告] 作业 '{hw_data.get('title')}' (课程: {course_name}) 因缺少截止日期而被跳过。")
                    continue
                end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')
                if end_time.hour == 0 and end_time.minute == 0:
                    end_time -= timedelta(minutes=1)
                homework_service.add_or_update_homework(db, user, course_name, hw_data['title'], end_time, hw_data['subStatus'])
        
        user.last_crawled_at = datetime.now()
        db.commit()
        print(f"[爬虫] 用户 {user.student_id} 的数据爬取完成。")
    except Exception as e:
        print(f"[爬虫] 处理用户 {user_id} 的任务时发生错误: {e}")
    finally:
        db.close()

def crawler_worker():
    """Worker that processes the crawl queue."""
    while True:
        if crawl_queue:
            user_id = crawl_queue.popleft()
            print(f"[工人] 从队列中取出用户 {user_id} 并开始爬取。")
            crawl_user_data(user_id)
        else:
            time.sleep(5)

def scheduler_loop():
    """The scheduler. Only adds user IDs to the crawl queue."""
    db: Session = next(get_db())
    print(f"[调度器] 运行中... 当前队列长度: {len(crawl_queue)}")
    try:
        hws_to_crawl = homework_service.get_homeworks_needing_crawl(db)
        for hw in hws_to_crawl:
            if hw.user_id not in crawl_queue:
                print(f"[调度器] 作业 '{hw.title}' 即将到期，将用户 {hw.user_id} 加入爬取队列。")
                crawl_queue.append(hw.user_id)

        users_to_refresh = user_service.get_users_needing_refresh(db)
        for user in users_to_refresh:
            if user.id not in crawl_queue:
                print(f"[调度器] 用户 {user.id} 的数据需要刷新，加入爬取队列。")
                crawl_queue.append(user.id)
    finally:
        db.close()

def notifier_loop():
    """The notifier. Only checks DB and sends emails."""
    db: Session = next(get_db())
    print("[通知器] 运行中...")
    try:
        users = user_service.get_all_active_users(db)
        for user in users:
            hws_to_remind = homework_service.get_homeworks_to_remind(db, user.id)
            if hws_to_remind:
                all_unsubmitted = homework_service.get_all_unsubmitted_homework(db, user.id)
                print(f"[通知器] 发现用户 {user.student_id} 有 {len(hws_to_remind)} 个作业需要提醒，准备发送邮件。")
                notification_service.send_email(
                    to_address=user.email, subject="作业提醒", template_name='email_template.html',
                    user=user, all_homework=all_unsubmitted, hws_to_remind=hws_to_remind
                )
                for hw in hws_to_remind:
                    if not hw.reminder_sent_1 and (hw.end_time - datetime.now()) <= timedelta(hours=user.reminder_threshold_1):
                        hw.reminder_sent_1 = True
                    if not hw.reminder_sent_2 and (hw.end_time - datetime.now()) <= timedelta(hours=user.reminder_threshold_2):
                        hw.reminder_sent_2 = True
                db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode.")
    args = parser.parse_args()

    init_db()

    if args.test:
        db = next(get_db())
        if not user_service.get_user_by_student_id(db, "23281001"):
            print("创建测试用户...")
            user_service.create_user(db, "23281001", "your_email@example.com", "default")
        db.close()
        
        print("\n--- 运行调度器 ---")
        scheduler_loop()
        print("\n--- 运行爬虫工人 ---")
        crawler_worker() # This will block until queue is empty
        print("\n--- 运行通知器 ---")
        notifier_loop()
    else:
        print("启动后台服务...")
        
        def run_scheduler():
            while True:
                scheduler_loop()
                time.sleep(60)

        def run_notifier():
            while True:
                notifier_loop()
                time.sleep(60)

        threading.Thread(target=crawler_worker, daemon=True).start()
        threading.Thread(target=run_scheduler, daemon=True).start()
        threading.Thread(target=run_notifier, daemon=True).start()

        # Keep main thread alive
        while True:
            time.sleep(3600)

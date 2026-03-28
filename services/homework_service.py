# services/homework_service.py

from sqlalchemy.orm import Session, joinedload
from models import Homework, User
from datetime import datetime, timedelta
import hashlib

def _get_user_advance_seconds(student_id: str) -> int:
    """Generates a deterministic advance time in seconds based on student ID."""
    # Use MD5 hash to get a consistent number for each student ID
    # The number will be between 0 and 3599 seconds (i.e., up to 60 minutes)
    if not student_id:
        return 0
    hash_object = hashlib.md5(student_id.encode())
    hex_dig = hash_object.hexdigest()
    return int(hex_dig, 16) % 3600

def get_homework_by_title_and_user(db: Session, title: str, user_id: int):
    return db.query(Homework).filter(Homework.title == title, Homework.user_id == user_id).first()

def add_or_update_homework(db: Session, user: User, course_name: str, title: str, end_time: datetime, status: str):
    db_homework = get_homework_by_title_and_user(db, title, user.id)
    if db_homework:
        # Reset flags if homework end time has changed
        if db_homework.end_time != end_time:
            db_homework.reminder_sent_1 = False
            db_homework.reminder_sent_2 = False
        db_homework.end_time = end_time
        db_homework.status = status
    else:
        db_homework = Homework(
            user_id=user.id,
            course_name=course_name,
            title=title,
            end_time=end_time,
            status=status
        )
        db.add(db_homework)
    db.commit()
    db.refresh(db_homework)
    return db_homework

def get_homeworks_needing_crawl(db: Session, user_id: int = None):
    """Gets homework that needs a status refresh based on a deterministic trigger time."""
    now = datetime.now()
    query = db.query(Homework).options(joinedload(Homework.user)).filter(
        Homework.end_time > now, 
        Homework.status != '已提交'
    )
    if user_id:
        query = query.filter(Homework.user_id == user_id)
    
    all_hws = query.all()
    hws_to_crawl = []

    for hw in all_hws:
        if not hw.user or not hw.user.is_active:
            continue

        # Calculate user-specific deterministic advance time
        advance_seconds = _get_user_advance_seconds(hw.user.student_id)
        advance_delta = timedelta(seconds=advance_seconds)

        # Check for threshold 1
        if not hw.reminder_sent_1:
            threshold_1_time = hw.end_time - timedelta(hours=hw.user.reminder_threshold_1)
            trigger_time_1 = threshold_1_time - advance_delta
            
            # Condition 1: Have we passed the trigger time?
            # Condition 2: Was the last crawl before the trigger time (i.e., have we not crawled for this event yet)?
            if now >= trigger_time_1 and (not hw.user.last_crawled_at or hw.user.last_crawled_at < trigger_time_1):
                hws_to_crawl.append(hw)
                continue # Move to next homework item to avoid double-adding

        # Check for threshold 2
        if not hw.reminder_sent_2:
            threshold_2_time = hw.end_time - timedelta(hours=hw.user.reminder_threshold_2)
            trigger_time_2 = threshold_2_time - advance_delta

            if now >= trigger_time_2 and (not hw.user.last_crawled_at or hw.user.last_crawled_at < trigger_time_2):
                hws_to_crawl.append(hw)

    return hws_to_crawl

def get_homeworks_to_remind(db: Session, user_id: int):
    """Gets homework that has passed the exact reminder threshold and needs a notification to be sent."""
    now = datetime.now()
    query = db.query(Homework).options(joinedload(Homework.user)).filter(
        Homework.user_id == user_id, 
        Homework.end_time > now, 
        Homework.status != '已提交'
    )
    
    all_hws = query.all()
    hws_to_remind = []
    for hw in all_hws:
        if not hw.user:
            continue

        # Check threshold 1 STRICTLY
        if not hw.reminder_sent_1 and (hw.end_time - now) <= timedelta(hours=hw.user.reminder_threshold_1):
            hws_to_remind.append(hw)
            continue
        
        # Check threshold 2 STRICTLY
        if not hw.reminder_sent_2 and (hw.end_time - now) <= timedelta(hours=hw.user.reminder_threshold_2):
            hws_to_remind.append(hw)

    return hws_to_remind

def get_all_unsubmitted_homework(db: Session, user_id: int):
    """Gets all unsubmitted and not expired homework for a user, sorted by end_time."""
    now = datetime.now()
    return db.query(Homework).filter(
        Homework.user_id == user_id,
        Homework.end_time > now,
        Homework.status != '已提交'
    ).order_by(Homework.end_time.asc()).all()
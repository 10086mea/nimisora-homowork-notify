# services/user_service.py

from sqlalchemy.orm import Session
from models import User
from datetime import datetime, timedelta
import random

def get_user_by_student_id(db: Session, student_id: str):
    return db.query(User).filter(User.student_id == student_id).first()

def create_user(db: Session, student_id: str, email: str, password_md5: str = None):
    processed_password = password_md5 if password_md5 else 'default'
    db_user = User(student_id=student_id, email=email, password_md5=processed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_all_active_users(db: Session):
    return db.query(User).filter(User.is_active == True).all()

def get_users_needing_refresh(db: Session):
    now = datetime.now()
    users_to_refresh = []
    for user in get_all_active_users(db):
        if not user.last_crawled_at:
            users_to_refresh.append(user)
            continue
        
        random_delay = timedelta(seconds=random.randint(0, 7200))
        if now > user.last_crawled_at + timedelta(hours=24) - random_delay:
            users_to_refresh.append(user)
            
    return users_to_refresh

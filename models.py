# models.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    student_id = Column(String(20), unique=True, nullable=False)
    email = Column(String(100), nullable=False)
    password_md5 = Column(String(32), nullable=True) # Can be null if using default
    reminder_threshold_1 = Column(Integer, default=48) # In hours
    reminder_threshold_2 = Column(Integer, default=24) # In hours
    is_active = Column(Boolean, default=True)
    last_crawled_at = Column(DateTime, nullable=True)

    homeworks = relationship('Homework', back_populates='user')

class Homework(Base):
    __tablename__ = 'homework'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    course_name = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False) # e.g., 'unsubmitted', 'submitted', 'graded'
    reminder_sent_1 = Column(Boolean, default=False)
    reminder_sent_2 = Column(Boolean, default=False)

    user = relationship('User', back_populates='homeworks')

# Example of how to create the database and tables
if __name__ == '__main__':
    from config import DATABASE_URL
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print("Database tables created.")

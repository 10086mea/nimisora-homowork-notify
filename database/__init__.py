# database/__init__.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Base

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database and creates tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Returns a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

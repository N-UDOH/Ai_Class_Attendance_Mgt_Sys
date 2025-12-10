# seed_db.py

from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db import SessionLocal, engine, Base
from app.models import User
from datetime import datetime

# Initialize password context (must match auth_router.py)
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def seed_users():
    Base.metadata.create_all(bind=engine) # Ensure tables exist
    db: Session = SessionLocal()
    
    # Define a common password to be hashed
    TEST_PASSWORD = "password123"
    hashed_password = get_password_hash(TEST_PASSWORD)

    # Test users (ensure you have these defined in your database)
    test_users = [
        # Lecturer 
        {"staff_no": "L1001", "name": "Dr. Smith (Lecturer)", "role": "lecturer", "password_hash": hashed_password},
        # Student
        {"staff_no": "S2023/101", "name": "Alice Johnson (Student)", "role": "student", "password_hash": hashed_password},
    ]

    # Check if users already exist to prevent duplicates
    if db.query(User).count() == 0:
        for user_data in test_users:
            new_user = User(**user_data)
            db.add(new_user)
        
        db.commit()
        print(f"Successfully created {len(test_users)} test users.")
        print(f"Login Password for all: {TEST_PASSWORD}")
    else:
        print("Database already contains users. Skipping seed process.")
        
    db.close()

if __name__ == "__main__":
    seed_users()
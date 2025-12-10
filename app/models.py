from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    staff_no = Column(String, unique=True, index=True) # Staff ID or Matric No
    name = Column(String)
    role = Column(String) # "lecturer" or "student"
    
    # --- NEW COLUMNS ---
    college = Column(String, nullable=True)
    department = Column(String, nullable=True)
    level = Column(String, nullable=True) # Only for students
    # -------------------

    password_hash = Column(String)

    # Relationships
    sessions = relationship("ClassSession", back_populates="creator")
    attendance_records = relationship("Attendance", back_populates="student")

class ClassSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id")) # The lecturer who created it
    
    course_code = Column(String)
    course_title = Column(String)
    
    # Geofencing Data
    latitude = Column(Float)
    longitude = Column(Float)
    radius_meters = Column(Integer)
    
    is_active = Column(Integer, default=1) # 1 = Active, 0 = Closed
    created_at = Column(DateTime)

    creator = relationship("User", back_populates="sessions")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime)

    student = relationship("User", back_populates="attendance_records")
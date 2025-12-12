from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    staff_no = Column(String, unique=True, index=True)
    name = Column(String)
    
    # --- CONTACT INFO ---
    email = Column(String, unique=True, index=True, nullable=True) 
    phone = Column(String, nullable=True)
    # --------------------

    role = Column(String) 
    college = Column(String, nullable=True)
    department = Column(String, nullable=True)
    level = Column(String, nullable=True)
    password_hash = Column(String)

    sessions = relationship("ClassSession", back_populates="creator")
    attendance_records = relationship("Attendance", back_populates="student")

class ClassSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    course_code = Column(String)
    course_title = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    radius_meters = Column(Integer)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime)

    creator = relationship("User", back_populates="sessions")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime)

    # --- SECURITY FINGERPRINTS ---
    ip_address = Column(String, nullable=True)     # To track the phone's network
    device_info = Column(String, nullable=True)    # To track the browser type
    is_manual = Column(Boolean, default=False)     # True if Lecturer added them manually
    flagged = Column(Boolean, default=False)       # True if caught cheating
    # -----------------------------

    student = relationship("User", back_populates="attendance_records")
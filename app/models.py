from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    staff_no = Column(String, unique=True, index=True)
    email = Column(String, nullable=True)  # ✅ Contains the Email
    role = Column(String)
    password = Column(String)              # ✅ Contains the Password
    college = Column(String)
    department = Column(String)
    level = Column(String, nullable=True)

class ClassSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_code = Column(String)
    course_title = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    radius_meters = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime)
    ip_address = Column(String, nullable=True)
    device_info = Column(String, nullable=True)
    is_manual = Column(Boolean, default=False)
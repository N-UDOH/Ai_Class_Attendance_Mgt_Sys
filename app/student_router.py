from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from haversine import haversine, Unit
from datetime import datetime

from app.db import SessionLocal
from app.models import User, ClassSession, Attendance
from app.dependencies import get_current_user

router = APIRouter(prefix="/student", tags=["student"])
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Core Logic: Distance Calculation ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance (in meters) between two points using Haversine."""
    point1 = (lat1, lon1)
    point2 = (lat2, lon2)
    distance_km = haversine(point1, point2, unit=Unit.KILOMETERS)
    distance_meters = distance_km * 1000
    return distance_meters


# --- 1. Dashboard/Check-in View (GET) ---
@router.get("/dashboard", response_class=HTMLResponse)
async def student_dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    student: User = Depends(get_current_user) # AUTH CHECK
):
    # Enforce role
    if student.role != "student":
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)

    # Extract status message from URL query parameters (for user feedback)
    status_message = request.query_params.get("status")

    active_sessions = db.query(ClassSession).filter(
        ClassSession.is_active == 1
    ).all()
    
    recent_attendance = db.query(Attendance).filter(
        Attendance.user_id == student.id
    ).order_by(Attendance.timestamp.desc()).limit(10).all()

    return templates.TemplateResponse("student_dashboard.html", {
        "request": request,
        "student": student,
        "active_sessions": active_sessions,
        "recent_attendance": recent_attendance,
        "status_message": status_message # Pass status message to template
    })


# --- 2. Check-in (POST) ---
@router.post("/check-in/{session_id}", response_class=RedirectResponse)
async def check_in(
    session_id: int,
    request: Request,
    student_latitude: float = Form(...),
    student_longitude: float = Form(...),
    db: Session = Depends(get_db),
    student: User = Depends(get_current_user) # AUTH CHECK
):
    if student.role != "student":
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)

    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()

    # 1. Check if session is active
    if not session or session.is_active == 0:
        return RedirectResponse("/student/dashboard?status=inactive", status_code=status.HTTP_302_FOUND)

    # 2. Check for duplicate attendance
    already_checked_in = db.query(Attendance).filter(
        Attendance.user_id == student.id,
        Attendance.session_id == session_id
    ).first()

    if already_checked_in:
        return RedirectResponse("/student/dashboard?status=duplicate", status_code=status.HTTP_302_FOUND) 
        
    # 3. Calculate distance
    distance_to_class = calculate_distance(
        session.latitude, 
        session.longitude,
        student_latitude, 
        student_longitude
    )
    
    # 4. Core AI/Geofencing Check
    if distance_to_class <= session.radius_meters:
        # Mark Attendance
        new_attendance = Attendance(
            session_id=session_id,
            user_id=student.id,
            timestamp=datetime.utcnow()
        )
        db.add(new_attendance)
        db.commit()
        
        return RedirectResponse("/student/dashboard?status=success", status_code=status.HTTP_302_FOUND)
    else:
        # Distance check failed
        return RedirectResponse("/student/dashboard?status=fail", status_code=status.HTTP_302_FOUND)
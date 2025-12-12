from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from haversine import haversine
from app.db import get_db
from app.models import User, ClassSession, Attendance

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 🎓 STUDENT DASHBOARD (SAFE MODE)
# ==========================================
@router.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request, db: Session = Depends(get_db)):
    # 1. Check Login
    user_id = request.session.get("user_id")
    if not user_id or request.session.get("user_role") != "student":
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # 2. Get Student (Ghost Cookie Protection)
    student = db.query(User).filter(User.id == user_id).first()
    if not student:
        request.session.clear()
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # 3. Find Active Session
    active_session = db.query(ClassSession).filter(ClassSession.is_active == True).first()
    
    # 4. Get Lecturer Name Safely (Separate Variable)
    lecturer_name = "Unknown Lecturer" 
    if active_session:
        lecturer = db.query(User).filter(User.id == active_session.user_id).first()
        if lecturer:
            lecturer_name = lecturer.name

    # 5. Render Page (Sending items separately)
    return templates.TemplateResponse("student_dashboard.html", {
        "request": request,
        "user": student,                 # ✅ Fixed: Sending User
        "active_session": active_session,
        "lecturer_name": lecturer_name   # ✅ Fixed: Sending Name separately
    })

# ==========================================
# 🚀 CHECK-IN ROUTE
# ==========================================
@router.post("/student/check-in/{session_id}")
async def check_in(
    request: Request, 
    session_id: int, 
    lat: float = Form(...), 
    long: float = Form(...), 
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # A. Get User and Session
    student = db.query(User).filter(User.id == user_id).first()
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()

    if not session or session.is_active == 0:
        return templates.TemplateResponse("student_dashboard.html", {
            "request": request, "user": student, "error": "Session is closed or invalid."
        })

    # B. SECURITY CHECK: Device Fingerprinting
    client_ip = request.client.host
    user_agent = request.headers.get('user-agent')

    duplicate_device = db.query(Attendance).filter(
        Attendance.session_id == session_id,
        Attendance.ip_address == client_ip,
        Attendance.device_info == user_agent,
        Attendance.user_id != user_id
    ).first()

    if duplicate_device:
        return templates.TemplateResponse("student_dashboard.html", {
            "request": request, 
            "user": student, 
            "error": "⛔ SECURITY ALERT: This device has already been used to sign in another student."
        })

    # C. Calculate Distance
    distance = haversine((lat, long), (session.latitude, session.longitude)) * 1000
    
    if distance > session.radius_meters:
        return templates.TemplateResponse("student_dashboard.html", {
            "request": request, "user": student, 
            "error": f"❌ You are too far! Distance: {int(distance)}m. Get closer to class."
        })

    # D. Mark Attendance
    existing = db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.session_id == session_id).first()
    if not existing:
        new_record = Attendance(
            session_id=session_id, 
            user_id=user_id, 
            timestamp=datetime.now(),
            ip_address=client_ip,
            device_info=user_agent,
            is_manual=False
        )
        db.add(new_record)
        db.commit()

    return templates.TemplateResponse("success.html", {"request": request, "user": student})
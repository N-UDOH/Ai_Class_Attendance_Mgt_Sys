import csv
import io
from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User, ClassSession, Attendance 
from app.dependencies import get_current_user

router = APIRouter(prefix="/lecturer", tags=["lecturer"])
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. Dashboard View (GET) ---
@router.get("/dashboard")
async def lecturer_dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    lecturer: User = Depends(get_current_user)
):
    if lecturer.role != "lecturer":
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

    sessions = db.query(ClassSession).filter(
        ClassSession.user_id == lecturer.id
    ).order_by(ClassSession.created_at.desc()).all()
    
    return templates.TemplateResponse("lecturer_dashboard.html", {
        "request": request,
        "lecturer": lecturer,
        "sessions": sessions
    })


# --- 2. Create Session (POST) ---
@router.post("/create-session", response_class=RedirectResponse)
async def create_session(
    request: Request,
    course_code: str = Form(...),
    course_title: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    radius_meters: float = Form(...),
    db: Session = Depends(get_db),
    lecturer: User = Depends(get_current_user)
):
    if lecturer.role != "lecturer":
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

    new_session = ClassSession(
        user_id=lecturer.id,
        course_code=course_code,
        course_title=course_title,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        is_active=1,
        created_at=datetime.utcnow()
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)


# --- 3. Close Session (POST) ---
@router.post("/close-session/{session_id}", response_class=RedirectResponse)
async def close_session(
    session_id: int, 
    db: Session = Depends(get_db),
    lecturer: User = Depends(get_current_user)
):
    if lecturer.role != "lecturer":
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

    session_to_close = db.query(ClassSession).filter(
        ClassSession.id == session_id
    ).first()
    
    if session_to_close and session_to_close.user_id == lecturer.id:
        session_to_close.is_active = 0
        db.commit()
    
    return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)


# --- 4. View Attendance Report (GET) ---
@router.get("/report/{session_id}")
async def view_report(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    lecturer: User = Depends(get_current_user)
):
    if lecturer.role != "lecturer":
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

    # 1. Fetch the specific session details
    session = db.query(ClassSession).filter(
        ClassSession.id == session_id,
        ClassSession.user_id == lecturer.id
    ).first()

    if not session:
        return templates.TemplateResponse("lecturer_dashboard.html", {
            "request": request, "lecturer": lecturer, "sessions": [], "error": "Session not found"
        })

    # 2. Fetch all attendance records for this session
    attendance_records = db.query(Attendance, User).join(
        User, Attendance.user_id == User.id
    ).filter(
        Attendance.session_id == session_id
    ).order_by(Attendance.timestamp.asc()).all()
    
    # 3. Process records
    report_list = [
        {
            "staff_no": user.staff_no,
            "name": user.name,
            "timestamp": attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        for attendance, user in attendance_records
    ]

    return templates.TemplateResponse("attendance_report.html", {
        "request": request,
        "session": session,
        "report_list": report_list
    })


# --- 5. Export Report to CSV (GET) ---
@router.get("/export/{session_id}")
async def export_report(
    session_id: int,
    db: Session = Depends(get_db),
    lecturer: User = Depends(get_current_user)
):
    if lecturer.role != "lecturer":
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

    # 1. Fetch Session Info
    session = db.query(ClassSession).filter(
        ClassSession.id == session_id,
        ClassSession.user_id == lecturer.id
    ).first()

    if not session:
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_404_NOT_FOUND)

    # 2. Fetch Attendance Records
    attendance_records = db.query(Attendance, User).join(
        User, Attendance.user_id == User.id
    ).filter(
        Attendance.session_id == session_id
    ).order_by(Attendance.timestamp.asc()).all()

    # 3. Create CSV in memory
    stream = io.StringIO()
    csv_writer = csv.writer(stream)

    # Write Header
    csv_writer.writerow(["Matric/Staff No", "Student Name", "Check-in Time", "Course Code"])

    # Write Data Rows
    for attendance, user in attendance_records:
        csv_writer.writerow([
            user.staff_no, 
            user.name, 
            attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            session.course_code
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    
    # Set filename
    filename = f"Attendance_{session.course_code}_{session.id}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    
    return response
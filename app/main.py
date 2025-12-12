from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from haversine import haversine

from app.db import engine, Base, SessionLocal
from app.models import User, ClassSession, Attendance
from app.auth_router import router as auth_router
from app.lecturer_router import router as lecturer_router
from app.student_router import router as student_router

# 1. Define Middleware List (Keep your secret key safe!)
middleware = [
    Middleware(SessionMiddleware, secret_key="YOUR_VERY_STRONG_SECRET_KEY_HERE_2025")
]

# 2. Create the FastAPI app
app = FastAPI(middleware=middleware)

# Create database tables
Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="app/templates")

# Include Routers (Auth, etc.)
app.include_router(auth_router)
app.include_router(lecturer_router)
app.include_router(student_router)

# --- DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 🚀 FEATURE 1: STRICT SECURITY CHECK-IN
# ==========================================
@app.post("/student/check-in/{session_id}")
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
    # Capture IP and Browser Info
    client_ip = request.client.host
    user_agent = request.headers.get('user-agent')

    # Check if this exact device was already used for this session by SOMEONE ELSE
    duplicate_device = db.query(Attendance).filter(
        Attendance.session_id == session_id,
        Attendance.ip_address == client_ip,       # Same IP
        Attendance.device_info == user_agent,     # Same Browser
        Attendance.user_id != user_id             # Different Student
    ).first()

    if duplicate_device:
        # 🛑 BLOCK THE ATTEMPT
        return templates.TemplateResponse("student_dashboard.html", {
            "request": request, 
            "user": student, 
            "error": "⛔ SECURITY ALERT: This device has already been used to sign in another student. You must use your own phone."
        })

    # C. Calculate Distance (Geofencing)
    # Compare Student GPS (lat, long) vs Class GPS (session.latitude, session.longitude)
    distance = haversine((lat, long), (session.latitude, session.longitude)) * 1000  # Convert km to meters
    
    if distance > session.radius_meters:
        return templates.TemplateResponse("student_dashboard.html", {
            "request": request, "user": student, 
            "error": f"❌ You are too far! Distance: {int(distance)}m. Get closer to class."
        })

    # D. Mark Attendance (If passed all checks)
    existing = db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.session_id == session_id).first()
    if not existing:
        new_record = Attendance(
            session_id=session_id, 
            user_id=user_id, 
            timestamp=datetime.now(),
            ip_address=client_ip,       # Save Fingerprint
            device_info=user_agent,     # Save Fingerprint
            is_manual=False
        )
        db.add(new_record)
        db.commit()

    return templates.TemplateResponse("success.html", {"request": request, "user": student})


# ==========================================
# 🔧 FEATURE 2: LECTURER MANUAL OVERRIDE
# ==========================================
@app.post("/lecturer/manual-add/{session_id}")
async def manual_add_student(
    request: Request, 
    session_id: int, 
    staff_no: str = Form(...), 
    db: Session = Depends(get_db)
):
    # Verify Lecturer is logged in
    if request.session.get("user_role") != "lecturer":
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # Find the student by Matric No
    student = db.query(User).filter(User.staff_no == staff_no, User.role == "student").first()
    
    if not student:
        # If student not found, just reload dashboard (you could add an error message here)
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)

    # Check if already present
    existing = db.query(Attendance).filter(Attendance.user_id == student.id, Attendance.session_id == session_id).first()
    if not existing:
        new_record = Attendance(
            session_id=session_id, 
            user_id=student.id, 
            timestamp=datetime.now(),
            is_manual=True,                 # <-- Mark as Manual Override
            ip_address="MANUAL_OVERRIDE",
            device_info="LECTURER_DASHBOARD"
        )
        db.add(new_record)
        db.commit()

    return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)


# ==========================================
# 📊 FEATURE 3: RISK ANALYTICS REPORT
# ==========================================
@app.get("/lecturer/report/{session_id}", response_class=HTMLResponse)
async def view_report(request: Request, session_id: int, db: Session = Depends(get_db)):
    # 1. Get the Session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        return "Session not found"

    # 2. Get students who attended THIS session
    attendees = db.query(Attendance, User).join(User, Attendance.user_id == User.id)\
                  .filter(Attendance.session_id == session_id).all()

    # 3. ANALYTICS ENGINE: Calculate Risk Scores
    student_data = []
    
    # Count TOTAL sessions held for this Course Code by this Lecturer
    total_classes_count = db.query(ClassSession).filter(
        ClassSession.course_code == session.course_code,
        ClassSession.user_id == request.session.get("user_id")
    ).count()

    if total_classes_count == 0:
        total_classes_count = 1 

    for attendance_record, student in attendees:
        # Count how many times THIS student attended THIS course
        student_attendance_count = db.query(Attendance).join(ClassSession)\
            .filter(
                Attendance.user_id == student.id,
                ClassSession.course_code == session.course_code
            ).count()

        # Calculate Percentage
        attendance_percent = round((student_attendance_count / total_classes_count) * 100, 1)

        # AI Risk Logic
        if attendance_percent >= 75:
            status_text = "Safe"
            color = "green"
        elif attendance_percent >= 50:
            status_text = "Warning"
            color = "#ffc107" # Amber
        else:
            status_text = "CRITICAL RISK"
            color = "red"

        student_data.append({
            "name": student.name,
            "staff_no": student.staff_no,
            "college": student.college,
            "department": student.department,
            "timestamp": attendance_record.timestamp,
            "percentage": attendance_percent,
            "status": status_text,
            "color": color,
            "is_manual": attendance_record.is_manual # Show if they were manually added
        })

    return templates.TemplateResponse("report.html", {
        "request": request,
        "session": session,
        "students": student_data,
        "total_classes": total_classes_count
    })


# --- ROOT LOGIN PAGE ---
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Checks for an active session and redirects, otherwise serves the login page."""
    if request.session.get('user_id'):
        role = request.session.get('user_role')
        if role == 'lecturer':
            return RedirectResponse("/lecturer/dashboard", status_code=302)
        else:
            return RedirectResponse("/student/dashboard", status_code=302)
            
    return templates.TemplateResponse("login.html", {"request": request})
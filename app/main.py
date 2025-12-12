from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from haversine import haversine
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

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
# 🎓 STUDENT DASHBOARD ROUTE (BULLETPROOF FIX)
# ==========================================
@app.get("/student/dashboard")
async def student_dashboard(request: Request, db: Session = Depends(get_db)):
    # 1. Check if session cookie exists
    user_id = request.session.get("user_id")
    if not user_id or request.session.get("user_role") != "student":
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # 2. Get Student Info
    student = db.query(User).filter(User.id == user_id).first()
    
    # 🚨 GHOST COOKIE FIX: If cookie exists but User is missing (deleted DB)
    if not student:
        request.session.clear()  # Kill the ghost cookie
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # 3. Find Active Session (if any)
    active_session = db.query(ClassSession).filter(ClassSession.is_active == True).first()
    
    # 4. Attach Lecturer Name if a session exists
    if active_session:
        lecturer = db.query(User).filter(User.id == active_session.user_id).first()
        # We perform a "monkey patch" to add the name to the object temporarily
        active_session.lecturer_name = lecturer.name if lecturer else "Unknown Lecturer"

    # 5. Render Page with USER Data
    return templates.TemplateResponse("student_dashboard.html", {
        "request": request,
        "user": student,         # Sends student info to HTML
        "active_session": active_session
    })

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
        # If student not found, just reload dashboard
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


# ==========================================
# 📧 FEATURE 4: WEEKLY RISK ALERTS (REAL GMAIL SENDING)
# ==========================================
@app.post("/lecturer/send-alerts/{session_id}")
async def send_risk_alerts(request: Request, session_id: int, db: Session = Depends(get_db)):
    # 1. Verify Lecturer
    if request.session.get("user_role") != "lecturer":
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    # 2. Get Session & Lecturer Info
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    lecturer = db.query(User).filter(User.id == request.session.get("user_id")).first()
    
    # 3. Credentials from Render Environment
    SENDER_EMAIL = os.getenv("MAIL_USERNAME")
    SENDER_PASSWORD = os.getenv("MAIL_PASSWORD")

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return templates.TemplateResponse("lecturer_dashboard.html", {
            "request": request, "user": lecturer,
            "sessions": db.query(ClassSession).filter(ClassSession.user_id == lecturer.id).all(),
            "error": "❌ Error: System Email is not configured in Render Environment!"
        })

    # 4. Find Students
    attendees = db.query(User).join(Attendance).join(ClassSession)\
                  .filter(ClassSession.course_code == session.course_code).distinct().all()

    alerts_sent = 0
    
    # 5. Connect to Gmail Server
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
    except Exception as e:
        return templates.TemplateResponse("lecturer_dashboard.html", {
            "request": request, "user": lecturer,
            "sessions": db.query(ClassSession).filter(ClassSession.user_id == lecturer.id).all(),
            "error": f"❌ Email Connection Failed: {str(e)}"
        })

    # 6. Analyze & Send
    total_classes = db.query(ClassSession).filter(
        ClassSession.course_code == session.course_code,
        ClassSession.user_id == lecturer.id
    ).count()
    if total_classes == 0: total_classes = 1

    for student in attendees:
        attendance_count = db.query(Attendance).join(ClassSession)\
            .filter(Attendance.user_id == student.id, ClassSession.course_code == session.course_code).count()
        
        percent = (attendance_count / total_classes) * 100

        if percent < 50:
            alerts_sent += 1
            
            # Create Email
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = student.email
            msg["Cc"] = lecturer.email
            msg["Subject"] = f"⚠️ ACADEMIC WARNING: {session.course_code}"

            body = f"""
            Dear {student.name},

            Your attendance in {session.course_code} has dropped to {percent:.1f}%.
            This is below the required threshold.

            Please contact your lecturer, {lecturer.name}, immediately to discuss your standing.

            Regards,
            Wesley University AI Attendance System
            """
            msg.attach(MIMEText(body, "plain"))

            # Send to Student AND Cc Lecturer
            recipients = [student.email, lecturer.email]
            try:
                server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
            except Exception as e:
                print(f"Failed to send to {student.name}: {e}")

    server.quit()

    return templates.TemplateResponse("lecturer_dashboard.html", {
        "request": request,
        "user": lecturer,
        "sessions": db.query(ClassSession).filter(ClassSession.user_id == lecturer.id).order_by(ClassSession.created_at.desc()).all(),
        "alert_success": f"✅ Emails Sent! {alerts_sent} at-risk students have been notified (Copy sent to you)."
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
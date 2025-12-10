from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# UPDATED KEY HERE
STUDENT_REGISTRATION_KEY = "WESLEY-CS-2026" 

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- LOGIN & LOGOUT ---
@router.post("/login")
async def login(request: Request, staff_no: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.staff_no == staff_no).first()

    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})
    if not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})

    request.session['user_id'] = user.id
    request.session['user_role'] = user.role

    if user.role == "lecturer":
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

@router.get("/logout", response_class=RedirectResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

# --- REGISTRATION LOGIC ---
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user(
    request: Request,
    name: str = Form(...),
    staff_no: str = Form(...),
    college: str = Form(...),
    department: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    level: str = Form(None),
    secret_key: str = Form(None),
    db: Session = Depends(get_db)
):
    # 1. Verification Check for Students (With NEW KEY)
    if role == "student":
        if not secret_key or secret_key.upper() != STUDENT_REGISTRATION_KEY:
            return templates.TemplateResponse("register.html", {
                "request": request, 
                "error": "Access Denied: Invalid Student Registration Key."
            })
    elif role == "lecturer":
        secret_key = None 
        level = None 

    # 2. Check if user already exists
    existing_user = db.query(User).filter(User.staff_no == staff_no).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "Account with this Staff/Matric ID already exists!"
        })

    # 3. Create new user
    hashed_password = get_password_hash(password)
    new_user = User(
        staff_no=staff_no,
        name=name,
        role=role,
        college=college,
        department=department,
        level=level,
        password_hash=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
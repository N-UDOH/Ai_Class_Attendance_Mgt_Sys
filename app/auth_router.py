from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db import SessionLocal
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

STUDENT_REGISTRATION_KEY = "WESLEY-CS-2026"

@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    staff_no: str = Form(...),
    # email removed
    role: str = Form(...),
    password: str = Form(...),
    college: str = Form(...),
    department: str = Form(...),
    level: str = Form(None),
    secret_key: str = Form(None),
    db: Session = Depends(get_db)
):
    # 1. Check if User Exists
    existing_user = db.query(User).filter(User.staff_no == staff_no).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "❌ Account already exists! Please login."
        })

    # 2. Security Check for Students
    if role == 'student':
        if secret_key != STUDENT_REGISTRATION_KEY:
            return templates.TemplateResponse("register.html", {
                "request": request, 
                "error": "❌ Invalid Student Registration Key!"
            })

    # 3. Create User (No Email)
    hashed_password = pwd_context.hash(password)
    new_user = User(
        name=name,
        staff_no=staff_no,
        role=role,
        password=hashed_password,
        college=college,
        department=department,
        level=level
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return templates.TemplateResponse("login.html", {
        "request": request, 
        "success": "✅ Registration Successful! Please Login."
    })

@router.post("/login")
async def login(
    request: Request, 
    staff_no: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.staff_no == staff_no).first()

    if not user or not pwd_context.verify(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "❌ Invalid Staff Number or Password"
        })

    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["user_name"] = user.name

    if user.role == "lecturer":
        return RedirectResponse("/lecturer/dashboard", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse("/student/dashboard", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})
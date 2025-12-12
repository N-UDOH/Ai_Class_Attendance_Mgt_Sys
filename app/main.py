from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from haversine import haversine
import os

from app.db import engine, Base, SessionLocal
from app.models import User, ClassSession, Attendance
from app.auth_router import router as auth_router
from app.lecturer_router import router as lecturer_router
from app.student_router import router as student_router

middleware = [
    Middleware(SessionMiddleware, secret_key="YOUR_VERY_STRONG_SECRET_KEY_HERE_2025")
]

app = FastAPI(middleware=middleware)
Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router)
app.include_router(lecturer_router)
app.include_router(student_router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# NOTE: Student Dashboard Logic is now handled in student_router.py
# We only need the root login redirect here.

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get('user_id'):
        role = request.session.get('user_role')
        if role == 'lecturer':
            return RedirectResponse("/lecturer/dashboard", status_code=302)
        else:
            return RedirectResponse("/student/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})
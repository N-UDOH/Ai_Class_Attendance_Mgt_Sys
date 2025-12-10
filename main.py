from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from app.db import engine, Base
from app.auth_router import router as auth_router
from app.lecturer_router import router as lecturer_router
from app.student_router import router as student_router

# Create middleware list (USE A STRONG, UNIQUE SECRET KEY)
middleware = [
    Middleware(SessionMiddleware, secret_key="YOUR_VERY_STRONG_SECRET_KEY_HERE_2025")
]

# Create the FastAPI app with the middleware
app = FastAPI(middleware=middleware)

# Create database tables (if they don't exist)
Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="app/templates")

# Include Routers
app.include_router(auth_router)
app.include_router(lecturer_router)
app.include_router(student_router)

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Checks for an active session and redirects, otherwise serves the login page."""
    
    # Check if user is already logged in
    if request.session.get('user_id'):
        role = request.session.get('user_role')
        if role == 'lecturer':
            return RedirectResponse("/lecturer/dashboard", status_code=302)
        else:
            return RedirectResponse("/student/dashboard", status_code=302)
            
    return templates.TemplateResponse("login.html", {"request": request})
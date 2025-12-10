# app/dependencies.py

from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User

# Helper to get DB session (needed for dependency function)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Fetches the user object from the session ID, or redirects to login."""
    
    # 1. Get user_id from session
    user_id = request.session.get('user_id')
    
    # 2. Check for missing session data
    if not user_id:
        # Redirect to login page
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": "/"}
        )
        
    # 3. Fetch user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    # 4. Check for deleted/invalid user
    if not user:
        request.session.clear() # Clear invalid session
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="User not found",
            headers={"Location": "/"}
        )
        
    return user
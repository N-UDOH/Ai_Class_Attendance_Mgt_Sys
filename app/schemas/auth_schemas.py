from pydantic import BaseModel

class LoginRequest(BaseModel):
    staff_no: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

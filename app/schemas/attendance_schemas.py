from pydantic import BaseModel

class AttendanceRequest(BaseModel):
    session_id: int
    latitude: float
    longitude: float

from pydantic import BaseModel

class CreateSessionRequest(BaseModel):
    course_code: str
    course_title: str
    latitude: float
    longitude: float
    radius_meters: float

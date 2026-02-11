from datetime import datetime

from pydantic import BaseModel


class EnrollmentCreate(BaseModel):
    course_id: int


class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    course_id: int
    created_at: datetime

    class Config:
        from_attributes = True

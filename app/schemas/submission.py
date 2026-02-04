from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SubmissionCreate(BaseModel):
    content: str

class SubmissionRead(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    content: str
    submitted_at: datetime
    grade: Optional[int] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SubmissionGradeUpdate(BaseModel):
    grade: int
    feedback: Optional[str] = None
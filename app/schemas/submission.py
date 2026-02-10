from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SubmissionCreate(BaseModel):
    content: Optional[str] = None


class SubmissionRead(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    content: Optional[str]
    submitted_at: datetime
    score: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubmissionGradeUpdate(BaseModel):
    score: float
    feedback: Optional[str] = None
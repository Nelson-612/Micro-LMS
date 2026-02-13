from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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

    # NEW computed fields
    is_late: bool = False
    late_by_minutes: Optional[int] = None

    class Config:
        from_attributes = True


class SubmissionGradeUpdate(BaseModel):
    score: float
    feedback: Optional[str] = None

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class GradebookRow(BaseModel):
    student_id: int
    student_email: str

    assignment_id: int
    assignment_title: str

    submitted_at: Optional[datetime] = None
    grade: Optional[int] = None
    feedback: Optional[str] = None
    status: str  # "missing" | "submitted" | "graded"
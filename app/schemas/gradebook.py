from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GradebookRow(BaseModel):
    student_id: int
    student_email: str

    assignment_id: int
    assignment_title: str

    submitted_at: Optional[datetime] = None
    grade: Optional[int] = None
    feedback: Optional[str] = None
    status: str  # "missing" | "submitted" | "graded"

    is_late: bool = False
    late_by_minutes: int | None = None

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CourseDashboardRow(BaseModel):
    course_id: int
    course_title: str
    total_assignments: int
    submitted: int
    missing: int
    graded: int
    average_grade: float | None
    next_due_at: Optional[datetime] = None
    next_due_title: Optional[str] = None
    next_due_is_overdue: bool = False
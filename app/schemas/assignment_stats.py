from pydantic import BaseModel


class AssignmentStatsRow(BaseModel):
    assignment_id: int
    assignment_title: str
    total_students: int
    submitted: int
    graded: int
    missing: int
    average_grade: float | None

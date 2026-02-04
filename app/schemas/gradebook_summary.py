from pydantic import BaseModel

class GradebookStudentSummary(BaseModel):
    student_id: int
    student_email: str
    total_assignments: int
    missing: int
    submitted: int
    graded: int
    average_grade: float | None
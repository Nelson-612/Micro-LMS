from pydantic import BaseModel

class InstructorCourseStats(BaseModel):
    course_id: int
    course_title: str
    total_students: int
    total_assignments: int
    total_submissions: int
    ungraded_submissions: int
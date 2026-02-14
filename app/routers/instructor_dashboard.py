from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.permissions import require_instructor
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.submission import Submission
from app.models.user import User
from app.schemas.instructor_dashboard import InstructorCourseStats

router = APIRouter(tags=["instructor"])


@router.get("/instructor/dashboard", response_model=list[InstructorCourseStats])
def instructor_dashboard(
    db: Session = Depends(get_db),
    me: User = Depends(require_instructor),
):
    courses = db.query(Course).filter(Course.instructor_id == me.id).all()

    rows: list[InstructorCourseStats] = []

    for course in courses:
        total_students = (
            db.query(func.count(Enrollment.id))
            .filter(Enrollment.course_id == course.id)
            .scalar()
        ) or 0

        total_assignments = (
            db.query(func.count(Assignment.id))
            .filter(Assignment.course_id == course.id)
            .scalar()
        ) or 0

        total_submissions = (
            db.query(func.count(Submission.id))
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .filter(Assignment.course_id == course.id)
            .scalar()
        ) or 0

        ungraded_submissions = (
            db.query(func.count(Submission.id))
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .filter(
                Assignment.course_id == course.id,
                Submission.score.is_(None),
            )
            .scalar()
        ) or 0

        rows.append(
            InstructorCourseStats(
                course_id=course.id,
                course_title=course.title,
                total_students=total_students,
                total_assignments=total_assignments,
                total_submissions=total_submissions,
                ungraded_submissions=ungraded_submissions,
            )
        )

    return rows

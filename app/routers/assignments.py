from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.current_user import get_current_user
from app.core.permissions import require_instructor
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User
from app.schemas.assignment import AssignmentCreate, AssignmentRead

router = APIRouter()

def _ensure_course_exists(db: Session, course_id: int) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

def _ensure_can_view_course_assignments(db: Session, course_id: int, user: User) -> None:
    # Instructor of the course can view
    is_instructor = db.query(Course).filter(Course.id == course_id, Course.instructor_id == user.id).first() is not None
    if is_instructor:
        return

    # Enrolled student can view
    is_enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.student_id == user.id
    ).first() is not None

    if not is_enrolled:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

@router.get("/courses/{course_id}/assignments", response_model=list[AssignmentRead])
def list_assignments(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_course_exists(db, course_id)
    _ensure_can_view_course_assignments(db, course_id, current_user)

    return db.query(Assignment).filter(Assignment.course_id == course_id).all()

@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    course_id: int,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    course = _ensure_course_exists(db, course_id)

    # optional: only the course instructor can create assignments
    if course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Only the course instructor can create assignments")

    a = Assignment(
        course_id=course_id,
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.core.deps import get_db
from app.core.current_user import get_current_user
from app.core.permissions import require_instructor
from app.models.user import User
from app.models.enrollment import Enrollment
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.submission import Submission
from app.schemas.submission import SubmissionCreate, SubmissionRead, SubmissionGradeUpdate

router = APIRouter()

def _get_assignment_or_404(db: Session, assignment_id: int) -> Assignment:
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a

def _ensure_enrolled(db: Session, course_id: int, student_id: int) -> None:
    enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.student_id == student_id
    ).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_assignment(
    assignment_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    a = _get_assignment_or_404(db, assignment_id)
    _ensure_enrolled(db, a.course_id, me.id)

    s = Submission(
        assignment_id=assignment_id,
        student_id=me.id,
        content=payload.content,
    )
    db.add(s)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already submitted")

    db.refresh(s)
    return s

@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionRead],
)
def list_submissions_for_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    a = _get_assignment_or_404(db, assignment_id)

    # Only the course instructor can view all submissions
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if not course or course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Not course instructor")

    return db.query(Submission).filter(Submission.assignment_id == assignment_id).all()

@router.get(
    "/submissions/me",
    response_model=list[SubmissionRead],
)
def my_submissions(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return db.query(Submission).filter(Submission.student_id == me.id).all()

@router.patch(
    "/submissions/{submission_id}",
    response_model=SubmissionRead,
)
def grade_submission(
    submission_id: int,
    payload: SubmissionGradeUpdate,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    s = db.query(Submission).filter(Submission.id == submission_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")

    a = _get_assignment_or_404(db, s.assignment_id)

    # Only course instructor can grade
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if not course or course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Not course instructor")

    s.grade = payload.grade
    s.feedback = payload.feedback
    s.graded_at = datetime.utcnow()

    db.commit()
    db.refresh(s)
    return s
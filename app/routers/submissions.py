from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.deps import get_db
from app.core.permissions import require_instructor
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionGradeUpdate,
    SubmissionRead,
)

router = APIRouter()


def _ensure_assignment_exists(db: Session, assignment_id: int) -> Assignment:
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def _ensure_student_enrolled(db: Session, course_id: int, student_id: int) -> None:
    enrolled = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id, Enrollment.student_id == student_id)
        .first()
        is not None
    )
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
    assignment = _ensure_assignment_exists(db, assignment_id)
    _ensure_student_enrolled(db, assignment.course_id, me.id)

    now = datetime.now(timezone.utc)

    # ✅ Step 2: deadline validation (block late submissions)
    if getattr(assignment, "due_at", None) is not None:
        due = assignment.due_at
        # normalize naive datetime to UTC
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)

        if now > due:
            raise HTTPException(status_code=400, detail="Assignment is past due")

    # allow resubmission: update existing submission if it exists
    existing = (
        db.query(Submission)
        .filter(
            and_(
                Submission.assignment_id == assignment_id,
                Submission.student_id == me.id,
            )
        )
        .first()
    )

    if existing:
        existing.content = payload.content
        existing.submitted_at = now

        # clear previous grading on resubmit (your policy choice)
        existing.score = None
        existing.feedback = None
        existing.graded_at = None

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(existing)
        return existing

    # otherwise create first submission
    s = Submission(
        assignment_id=assignment_id,
        student_id=me.id,
        content=payload.content,
        submitted_at=now,
    )
    db.add(s)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

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
    assignment = _ensure_assignment_exists(db, assignment_id)

    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    if not course or course.instructor_id != instructor.id:
        raise HTTPException(
            status_code=403,
            detail="Only the course instructor can view submissions",
        )

    return db.query(Submission).filter(Submission.assignment_id == assignment_id).all()


@router.patch(
    "/submissions/{submission_id}/grade",
    response_model=SubmissionRead,
)
def grade_submission(
    submission_id: int,
    payload: SubmissionGradeUpdate,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = db.query(Assignment).filter(Assignment.id == sub.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    if not course or course.instructor_id != instructor.id:
        raise HTTPException(
            status_code=403, detail="Only the course instructor can grade"
        )

    if payload.score < 0 or payload.score > assignment.max_score:
        raise HTTPException(
            status_code=400,
            detail=f"score must be between 0 and {assignment.max_score}",
        )

    sub.score = payload.score
    sub.feedback = payload.feedback
    sub.graded_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(sub)
    return sub

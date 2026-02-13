import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.config import GRACE_PERIOD_MINUTES, LATE_PENALTY_MAX, LATE_PENALTY_PER_DAY
from app.core.current_user import get_current_user
from app.core.deps import get_db
from app.core.permissions import require_instructor
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionGradeUpdate, SubmissionRead

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


def _late_penalty_multiplier(
    assignment: Assignment,
    submitted_at: datetime,
) -> tuple[bool, int | None, int, float]:
    """
    Returns: (is_late, late_by_minutes, days_late, multiplier)

    Policy:
    - GRACE_PERIOD_MINUTES: if late_by_minutes <= grace -> not late, no penalty
    - LATE_PENALTY_PER_DAY: percent off per day late
    - LATE_PENALTY_MAX: cap total deduction (0.50 means max 50% off)
    """
    if assignment.due_at is None:
        return (False, None, 0, 1.0)

    due = assignment.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)

    submitted = submitted_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)

    if submitted <= due:
        return (False, 0, 0, 1.0)

    late_minutes = int((submitted - due).total_seconds() // 60)

    # ✅ grace period
    if late_minutes <= GRACE_PERIOD_MINUTES:
        return (False, late_minutes, 0, 1.0)

    # compute days late (ceil, so 1 minute past grace counts as 1 day late)
    days_late = int(math.ceil(late_minutes / 1440)) if late_minutes > 0 else 0

    raw_deduction = days_late * LATE_PENALTY_PER_DAY
    capped_deduction = min(raw_deduction, LATE_PENALTY_MAX)

    multiplier = max(0.0, 1.0 - capped_deduction)
    return (True, late_minutes, days_late, multiplier)


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

    # ✅ Late detection using the SAME policy (grace window included)
    is_late, late_by_minutes, _days_late, _mult = _late_penalty_multiplier(assignment, now)

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

        # clear previous grading on resubmit (policy choice)
        existing.score = None
        existing.feedback = None
        existing.graded_at = None

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(existing)

        # attach computed fields
        existing.is_late = is_late
        existing.late_by_minutes = late_by_minutes
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

    # attach computed fields
    s.is_late = is_late
    s.late_by_minutes = late_by_minutes
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

    subs = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()

    # attach computed fields for response (uses submission time)
    for s in subs:
        is_late, late_by_minutes, _days_late, _mult = _late_penalty_multiplier(assignment, s.submitted_at)
        s.is_late = is_late
        s.late_by_minutes = late_by_minutes

    return subs


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
        raise HTTPException(status_code=403, detail="Only the course instructor can grade")

    if payload.score < 0 or payload.score > assignment.max_score:
        raise HTTPException(
            status_code=400,
            detail=f"score must be between 0 and {assignment.max_score}",
        )

    raw_score = payload.score

    # compute late penalty based on actual submitted time
    is_late, late_by_minutes, days_late, mult = _late_penalty_multiplier(
        assignment,
        sub.submitted_at,
    )

    final_score = round(raw_score * mult, 2)
    sub.score = final_score

    # add/merge feedback note if late (mention cap)
    note = None
    if is_late and days_late > 0:
        raw_deduction = days_late * LATE_PENALTY_PER_DAY
        capped_deduction = min(raw_deduction, LATE_PENALTY_MAX)
        penalty_pct = int(round(capped_deduction * 100))
        note = (
            f"Late penalty applied: -{penalty_pct}% "
            f"({days_late} day(s) late, grace {GRACE_PERIOD_MINUTES} min, cap {int(LATE_PENALTY_MAX*100)}%)."
        )

    if payload.feedback and note:
        sub.feedback = payload.feedback + "\n" + note
    elif payload.feedback:
        sub.feedback = payload.feedback
    elif note:
        sub.feedback = note
    else:
        sub.feedback = None

    sub.graded_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(sub)

    # attach computed fields for response
    sub.is_late = is_late
    sub.late_by_minutes = late_by_minutes
    return sub
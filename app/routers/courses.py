from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.core.config import GRACE_PERIOD_MINUTES
from app.core.current_user import get_current_user
from app.core.deps import get_db
from app.core.permissions import require_instructor
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.submission import Submission
from app.models.user import User
from app.schemas.assignment_stats import AssignmentStatsRow
from app.schemas.course import CourseCreate, CourseRead
from app.schemas.dashboard import CourseDashboardRow
from app.schemas.gradebook import GradebookRow
from app.schemas.gradebook_summary import GradebookStudentSummary

router = APIRouter()


def _gradebook_order_by():
    """
    Gradebook ordering:
    - Student email ascending
    - due_at NULLs last (SQLite-safe)
    - due_at ascending
    - assignment id ascending (stable tie-break)
    """
    return (
        User.email.asc(),
        Assignment.due_at.is_(None),  # NULLs last (SQLite-safe)
        Assignment.due_at.asc(),
        Assignment.id.asc(),
    )


def _assignment_order_by():
    """
    Assignment ordering (no User table involved):
    - due_at NULLs last (SQLite-safe)
    - due_at ascending
    - assignment id ascending
    """
    return (
        Assignment.due_at.is_(None),
        Assignment.due_at.asc(),
        Assignment.id.asc(),
    )


@router.get("/", response_model=list[CourseRead])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Course).all()


@router.post("/", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    course = Course(
        title=payload.title,
        description=payload.description,
        instructor_id=instructor.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/me", response_model=list[CourseRead])
def my_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == current_user.id)
        .all()
    )


@router.get("/{course_id}/gradebook", response_model=list[GradebookRow])
def course_gradebook(
    course_id: int,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    # verify course + ownership
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Not course instructor")

    rows = (
        db.query(
            User.id.label("student_id"),
            User.email.label("student_email"),
            Assignment.id.label("assignment_id"),
            Assignment.title.label("assignment_title"),
            Assignment.due_at.label("due_at"),
            Submission.submitted_at,
            Submission.score.label("grade"),
            Submission.feedback,
        )
        .join(Enrollment, Enrollment.student_id == User.id)
        .join(Assignment, Assignment.course_id == Enrollment.course_id)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == User.id,
            ),
        )
        .filter(Enrollment.course_id == course_id)
        .order_by(*_gradebook_order_by())
        .all()
    )

    result: list[dict] = []
    for r in rows:
        if r.submitted_at is None:
            status_val = "missing"
        elif r.grade is None:
            status_val = "submitted"
        else:
            status_val = "graded"

        # compute late flags for gradebook display
        is_late = False
        late_by_minutes = None

        if r.submitted_at is not None and r.due_at is not None:
            due = r.due_at
            submitted = r.submitted_at

            # SQLite often returns naive datetimes; treat as UTC
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if submitted.tzinfo is None:
                submitted = submitted.replace(tzinfo=timezone.utc)

            late_minutes = int((submitted - due).total_seconds() // 60)

            if late_minutes > 0:
                late_by_minutes = late_minutes
                # only mark "late" if beyond grace
                if late_minutes > GRACE_PERIOD_MINUTES:
                    is_late = True

        result.append(
            {
                "student_id": r.student_id,
                "student_email": r.student_email,
                "assignment_id": r.assignment_id,
                "assignment_title": r.assignment_title,
                "submitted_at": r.submitted_at,
                "grade": r.grade,
                "feedback": r.feedback,
                "status": status_val,
                "is_late": is_late,
                "late_by_minutes": late_by_minutes,
            }
        )

    return result


# ✅ Option A: student sees only THEIR rows
@router.get("/{course_id}/gradebook/me", response_model=list[GradebookRow])
def my_course_gradebook(
    course_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    # 1) course exists?
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # 2) enrolled?
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == me.id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    # 3) assignments in this course + this student's submission (if any)
    rows = (
        db.query(
            Assignment.id.label("assignment_id"),
            Assignment.title.label("assignment_title"),
            Assignment.due_at.label("due_at"),
            Submission.submitted_at,
            Submission.score.label("grade"),
            Submission.feedback,
        )
        .select_from(Assignment)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == me.id,
            ),
        )
        .filter(Assignment.course_id == course_id)
        .order_by(*_assignment_order_by())
        .all()
    )

    result: list[dict] = []
    for r in rows:
        if r.submitted_at is None:
            status_val = "missing"
        elif r.grade is None:
            status_val = "submitted"
        else:
            status_val = "graded"

        # compute late flags
        is_late = False
        late_by_minutes = None

        if r.submitted_at is not None and r.due_at is not None:
            due = r.due_at
            submitted = r.submitted_at

            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if submitted.tzinfo is None:
                submitted = submitted.replace(tzinfo=timezone.utc)

            late_minutes = int((submitted - due).total_seconds() // 60)

            if late_minutes > 0:
                late_by_minutes = late_minutes
                if late_minutes > GRACE_PERIOD_MINUTES:
                    is_late = True

        result.append(
            {
                "student_id": me.id,
                "student_email": me.email,
                "assignment_id": r.assignment_id,
                "assignment_title": r.assignment_title,
                "submitted_at": r.submitted_at,
                "grade": r.grade,
                "feedback": r.feedback,
                "status": status_val,
                "is_late": is_late,
                "late_by_minutes": late_by_minutes,
            }
        )

    return result


@router.get(
    "/{course_id}/gradebook/summary", response_model=list[GradebookStudentSummary]
)
def gradebook_summary(
    course_id: int,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Not course instructor")

    rows = (
        db.query(
            User.id.label("student_id"),
            User.email.label("student_email"),
            func.count(Assignment.id).label("total_assignments"),
            func.sum(case((Submission.id.is_(None), 1), else_=0)).label("missing"),
            func.sum(case((Submission.id.is_not(None), 1), else_=0)).label("submitted"),
            func.sum(case((Submission.score.is_not(None), 1), else_=0)).label("graded"),
            func.avg(Submission.score).label("average_grade"),
        )
        .join(Enrollment, Enrollment.student_id == User.id)
        .join(Assignment, Assignment.course_id == Enrollment.course_id)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == User.id,
            ),
        )
        .filter(Enrollment.course_id == course_id)
        .group_by(User.id, User.email)
        .order_by(User.email.asc())
        .all()
    )

    result: list[dict] = []
    for r in rows:
        avg = float(r.average_grade) if r.average_grade is not None else None
        result.append(
            {
                "student_id": r.student_id,
                "student_email": r.student_email,
                "total_assignments": int(r.total_assignments or 0),
                "missing": int(r.missing or 0),
                "submitted": int(r.submitted or 0),
                "graded": int(r.graded or 0),
                "average_grade": avg,
            }
        )
    return result


@router.get(
    "/{course_id}/gradebook/assignments", response_model=list[AssignmentStatsRow]
)
def gradebook_assignment_stats(
    course_id: int,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Not course instructor")

    total_students = (
        db.query(func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id)
        .scalar()
    ) or 0

    rows = (
        db.query(
            Assignment.id.label("assignment_id"),
            Assignment.title.label("assignment_title"),
            func.count(Submission.id).label("submitted"),
            func.sum(case((Submission.score.is_not(None), 1), else_=0)).label("graded"),
            func.avg(Submission.score).label("average_grade"),
        )
        .filter(Assignment.course_id == course_id)
        .outerjoin(Submission, Submission.assignment_id == Assignment.id)
        .group_by(Assignment.id, Assignment.title)
        .order_by(Assignment.id.asc())
        .all()
    )

    result: list[dict] = []
    for r in rows:
        submitted = int(r.submitted or 0)
        graded = int(r.graded or 0)
        missing = int(total_students - submitted)
        avg = float(r.average_grade) if r.average_grade is not None else None

        result.append(
            {
                "assignment_id": r.assignment_id,
                "assignment_title": r.assignment_title,
                "total_students": int(total_students),
                "submitted": submitted,
                "graded": graded,
                "missing": missing,
                "average_grade": avg,
            }
        )

    return result


@router.get("/me/dashboard", response_model=list[CourseDashboardRow])
def my_dashboard(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    courses = (
        db.query(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == me.id)
        .all()
    )

    result: list[dict] = []
    for c in courses:
        agg = (
            db.query(
                func.count(Assignment.id).label("total_assignments"),
                func.sum(case((Submission.id.is_not(None), 1), else_=0)).label(
                    "submitted"
                ),
                func.sum(case((Submission.id.is_(None), 1), else_=0)).label("missing"),
                func.sum(case((Submission.score.is_not(None), 1), else_=0)).label(
                    "graded"
                ),
                func.avg(Submission.score).label("average_grade"),
            )
            .select_from(Assignment)
            .outerjoin(
                Submission,
                and_(
                    Submission.assignment_id == Assignment.id,
                    Submission.student_id == me.id,
                ),
            )
            .filter(Assignment.course_id == c.id)
            .first()
        )

        total_assignments = int(agg.total_assignments or 0)
        submitted = int(agg.submitted or 0)
        missing = int(agg.missing or 0)
        graded = int(agg.graded or 0)
        avg = float(agg.average_grade) if agg.average_grade is not None else None

        # next due assignment the student has NOT submitted
        next_due = (
            db.query(Assignment)
            .outerjoin(
                Submission,
                and_(
                    Submission.assignment_id == Assignment.id,
                    Submission.student_id == me.id,
                ),
            )
            .filter(Assignment.course_id == c.id)
            .filter(Submission.id.is_(None))
            .filter(Assignment.due_at.is_not(None))
            .order_by(Assignment.due_at.asc())
            .first()
        )

        # overdue flag for next due assignment
        now = datetime.now(timezone.utc)
        next_due_is_overdue = False
        if next_due and next_due.due_at:
            due = next_due.due_at
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            next_due_is_overdue = due < now

        result.append(
            {
                "course_id": c.id,
                "course_title": c.title,
                "total_assignments": total_assignments,
                "submitted": submitted,
                "missing": missing,
                "graded": graded,
                "average_grade": avg,
                "next_due_at": next_due.due_at if next_due else None,
                "next_due_title": next_due.title if next_due else None,
                "next_due_is_overdue": next_due_is_overdue,
            }
        )

    return result

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

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
            Submission.submitted_at,
            Submission.grade,
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
        # optional:
        # .order_by(User.id, Assignment.id)
        .all()
    )

    result = []
    for r in rows:
        if r.submitted_at is None:
            status_val = "missing"
        elif r.grade is None:
            status_val = "submitted"
        else:
            status_val = "graded"

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

    # One row per student, aggregated across assignments
    rows = (
        db.query(
            User.id.label("student_id"),
            User.email.label("student_email"),
            func.count(Assignment.id).label("total_assignments"),
            func.sum(case((Submission.id.is_(None), 1), else_=0)).label("missing"),
            func.sum(case((Submission.id.is_not(None), 1), else_=0)).label("submitted"),
            func.sum(case((Submission.grade.is_not(None), 1), else_=0)).label("graded"),
            func.avg(Submission.grade).label("average_grade"),
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
        .order_by(User.id)
        .all()
    )

    # Convert avg to float (SQLite may return Decimal/None)
    result = []
    for r in rows:
        avg = float(r.average_grade) if r.average_grade is not None else None
        result.append(
            {
                "student_id": r.student_id,
                "student_email": r.student_email,
                "total_assignments": r.total_assignments,
                "missing": r.missing,
                "submitted": r.submitted,
                "graded": r.graded,
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

    total_students_subq = (
        db.query(func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id)
        .scalar()
    )

    rows = (
        db.query(
            Assignment.id.label("assignment_id"),
            Assignment.title.label("assignment_title"),
            func.count(Submission.id).label("submitted"),
            func.sum(case((Submission.grade.is_not(None), 1), else_=0)).label("graded"),
            func.avg(Submission.grade).label("average_grade"),
        )
        .filter(Assignment.course_id == course_id)
        .outerjoin(Submission, Submission.assignment_id == Assignment.id)
        .group_by(Assignment.id, Assignment.title)
        .order_by(Assignment.id)
        .all()
    )

    result = []
    for r in rows:
        submitted = int(r.submitted or 0)
        graded = int(r.graded or 0)
        missing = int(total_students_subq - submitted)
        avg = float(r.average_grade) if r.average_grade is not None else None

        result.append(
            {
                "assignment_id": r.assignment_id,
                "assignment_title": r.assignment_title,
                "total_students": int(total_students_subq),
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
    # courses the student is enrolled in
    courses = (
        db.query(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == me.id)
        .all()
    )

    result = []

    for c in courses:
        # aggregate counts for this student in this course
        agg = (
            db.query(
                func.count(Assignment.id).label("total_assignments"),
                func.sum(case((Submission.id.is_not(None), 1), else_=0)).label(
                    "submitted"
                ),
                func.sum(case((Submission.id.is_(None), 1), else_=0)).label("missing"),
                func.sum(case((Submission.grade.is_not(None), 1), else_=0)).label(
                    "graded"
                ),
                func.avg(Submission.grade).label("average_grade"),
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
            # SQLite often returns naive datetimes; treat as UTC for now
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

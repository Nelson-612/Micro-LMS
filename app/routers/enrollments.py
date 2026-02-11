from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user  # adjust if needed
from app.db.session import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut

router = APIRouter()


@router.post("", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
def enroll_me(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = Enrollment(student_id=me.id, course_id=payload.course_id)
    db.add(enrollment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already enrolled")

    db.refresh(enrollment)
    return enrollment


@router.get("/me", response_model=list[EnrollmentOut])
def my_enrollments(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    return db.query(Enrollment).filter(Enrollment.student_id == me.id).all()

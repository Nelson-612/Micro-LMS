import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.main import app
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User

TEST_DB_FILE = "test_micro_lms.db"
TEST_DB_URL = f"sqlite:///./{TEST_DB_FILE}"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create a fresh schema once for the whole test session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


@pytest.fixture(autouse=True)
def seed_data():
    """Seed a clean minimal dataset for each test."""
    db = TestingSessionLocal()
    try:
        # Clear tables (child -> parent)
        db.query(Enrollment).delete()
        db.query(Assignment).delete()
        db.query(Course).delete()
        db.query(User).delete()
        db.commit()

        # Users
        student = User(
            email="student1@example.com",
            full_name="Student One",
            role="student",
            hashed_password=hash_password("password123"),
        )
        instructor = User(
            email="instructor1@example.com",
            full_name="Instructor One",
            role="instructor",
            hashed_password=hash_password("password123"),
        )
        db.add_all([student, instructor])
        db.commit()
        db.refresh(student)
        db.refresh(instructor)

        # Course
        course = Course(
            title="CS5004",
            instructor_id=instructor.id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)

        # Enrollment
        db.add(Enrollment(course_id=course.id, student_id=student.id))
        db.commit()

        # Assignment (future due date so submissions allowed)
        db.add(
            Assignment(
                course_id=course.id,
                title="HW1",
                due_at=datetime.now(timezone.utc) + timedelta(days=1),
                max_score=100,
            )
        )
        db.commit()

        yield
    finally:
        db.close()


@pytest.fixture()
def client():
    """Test client that uses the test DB session via dependency override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

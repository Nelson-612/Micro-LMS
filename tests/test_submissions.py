from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import GRACE_PERIOD_MINUTES
from app.models.assignment import Assignment


def login(client, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_submit_and_resubmit_updates_same_row(client):
    student = login(client, "student1@example.com", "password123")

    r1 = client.post(
        "/assignments/1/submissions",
        headers=auth_header(student),
        json={"content": "first"},
    )
    assert r1.status_code == 201, r1.text
    id1 = r1.json()["id"]

    r2 = client.post(
        "/assignments/1/submissions",
        headers=auth_header(student),
        json={"content": "second"},
    )
    assert r2.status_code == 201, r2.text
    body2 = r2.json()
    assert body2["id"] == id1
    assert body2["content"] == "second"


def test_late_submission_is_allowed_and_marked_late(client):
    student = login(client, "student1@example.com", "password123")

    # force assignment 1 due date to the past in the test DB
    from tests.conftest import TestingSessionLocal  # reuse test session factory

    db: Session = TestingSessionLocal()
    try:
        a = db.query(Assignment).filter(Assignment.id == 1).first()
        assert a is not None
        a.due_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/assignments/1/submissions",
        headers=auth_header(student),
        json={"content": "late"},
    )

    # ✅ new policy: late submissions allowed
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["is_late"] is True
    assert body["late_by_minutes"] is not None
    assert body["late_by_minutes"] > GRACE_PERIOD_MINUTES

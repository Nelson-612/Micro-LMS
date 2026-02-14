import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def login(email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def instructor_token():
    # adjust if your seed users differ
    return login("instructor1@example.com", "password123")


@pytest.fixture(scope="module")
def student_token():
    return login("student1@example.com", "password123")


def test_student_cannot_view_instructor_gradebook(student_token):
    r = client.get("/courses/1/gradebook", headers=auth_header(student_token))
    assert r.status_code == 403


def test_instructor_can_view_gradebook(instructor_token):
    r = client.get("/courses/1/gradebook", headers=auth_header(instructor_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_student_can_view_my_gradebook(student_token):
    r = client.get("/courses/1/gradebook/me", headers=auth_header(student_token))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # each row should belong to the logged-in student
    assert all(row["student_email"] == "student1@example.com" for row in data)


def test_gradebook_rows_have_late_fields(instructor_token):
    r = client.get("/courses/1/gradebook", headers=auth_header(instructor_token))
    assert r.status_code == 200
    rows = r.json()
    if rows:
        assert "is_late" in rows[0]
        assert "late_by_minutes" in rows[0]

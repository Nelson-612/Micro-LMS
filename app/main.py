from fastapi import FastAPI

from app.db.init_db import init_db

from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.courses import router as courses_router
from app.routers.enrollments import router as enrollments_router
from app.routers.assignments import router as assignments_router
from app.routers.submissions import router as submissions_router

app = FastAPI(title="Micro LMS")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    init_db()


# Auth routes
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Admin routes
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# Courses routes
app.include_router(courses_router, prefix="/courses", tags=["courses"])

# Enrollments routes
app.include_router(enrollments_router, prefix="/enrollments", tags=["enrollments"])

# Assignments routes
app.include_router(assignments_router, tags=["assignments"])

# Submissions routes
app.include_router(submissions_router, tags=["submissions"])
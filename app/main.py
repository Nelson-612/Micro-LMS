import logging

from fastapi import FastAPI

from app.core.logging_middleware import LoggingMiddleware
from app.db.init_db import init_db

# Import routers directly (bulletproof way)
from app.routers.admin import router as admin_router
from app.routers.assignments import router as assignments_router
from app.routers.auth import router as auth_router
from app.routers.courses import router as courses_router
from app.routers.enrollments import router as enrollments_router
from app.routers.instructor_dashboard import router as instructor_dashboard_router
from app.routers.submissions import router as submissions_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Micro LMS")

# Middleware
app.add_middleware(LoggingMiddleware)


# Health check
@app.get("/health")
def health():
    return {"status": "ok"}


# Startup event
@app.on_event("startup")
def on_startup():
    init_db()


# Include routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(courses_router, prefix="/courses", tags=["courses"])
app.include_router(enrollments_router, prefix="/enrollments", tags=["enrollments"])
app.include_router(assignments_router, tags=["assignments"])
app.include_router(submissions_router, tags=["submissions"])

# Instructor dashboard (no prefix — route already defines full path)
app.include_router(instructor_dashboard_router)

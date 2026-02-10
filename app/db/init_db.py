from app.db.session import engine
from app.db.base import Base

# import models so SQLAlchemy registers them
from app.models import user, course, enrollment, assignment, submission  # noqa: F401

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
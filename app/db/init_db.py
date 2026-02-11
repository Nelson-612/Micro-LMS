from app.db.base import Base
from app.db.session import engine

# import models so SQLAlchemy registers them
from app.models import assignment, course, enrollment, submission, user  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

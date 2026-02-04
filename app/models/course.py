from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from sqlalchemy.orm import relationship

class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instructor_id: Mapped[int] = mapped_column(nullable=False, index=True)

    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")

    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")
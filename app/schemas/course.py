from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CourseRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    instructor_id: int

    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    id: int
    title: str
    description: str | None
    instructor_id: int

    class Config:
        from_attributes = True

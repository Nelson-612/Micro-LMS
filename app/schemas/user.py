from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = None


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    role: str

    class Config:
        from_attributes = True

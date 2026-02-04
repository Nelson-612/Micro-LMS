from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None

class AssignmentRead(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str]
    due_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
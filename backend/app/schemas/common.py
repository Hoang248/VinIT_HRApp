from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
from uuid import UUID


class BaseSchema(BaseModel):
    class Config:
        from_attributes = True
        populate_by_name = True


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class OperationResponse(BaseModel):
    operation_id: UUID
    status: str  # pending, processing, completed, failed
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

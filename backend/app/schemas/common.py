"""
Common response schemas.

Provides a consistent API response envelope used by all endpoints.
Every response wraps its payload in either SuccessResponse or ErrorResponse.
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response envelope."""

    success: bool = True
    data: Optional[DataT] = None
    message: str = "OK"

    model_config = {"arbitrary_types_allowed": True}


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool = False
    error: str
    code: str

    model_config = {"json_schema_extra": {
        "example": {
            "success": False,
            "error": "Invalid credentials.",
            "code": "INVALID_CREDENTIALS",
        }
    }}


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    total: int = Field(..., description="Total number of items matching the query")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated list response with metadata."""

    success: bool = True
    data: List[DataT]
    meta: PaginationMeta
    message: str = "OK"

    model_config = {"arbitrary_types_allowed": True}


def ok(data: Any = None, message: str = "OK") -> dict:
    """
    Shorthand helper for building a success response dict.

    Usage:
        return ok(data=user_schema, message="User created successfully.")
    """
    return {"success": True, "data": data, "message": message}


def err(error: str, code: str) -> dict:
    """
    Shorthand helper for building an error response dict.

    Usage:
        return err("Email already registered.", "EMAIL_EXISTS")
    """
    return {"success": False, "error": error, "code": code}

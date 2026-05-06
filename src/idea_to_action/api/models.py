"""API request and response models for idea-to-action."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SubmitRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, description="Raw user notes to process")
    input_type: str = Field(default="other", description="Input type hint")


class ErrorDetail(BaseModel):
    step: str
    message: str
    error_type: str


class SubmitResponse(BaseModel):
    trace_id: str
    status: str  # "success" or "partial"
    input_text: str
    organized: Optional[dict[str, Any]] = None
    plan: Optional[dict[str, Any]] = None
    tool_actions: Optional[dict[str, Any]] = None
    errors: list[ErrorDetail] = Field(default_factory=list)
    processed_at: str


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_available: bool


class ErrorResponse(BaseModel):
    detail: str
    error_type: str

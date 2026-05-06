"""FastAPI application factory for idea-to-action."""

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from idea_to_action.agent.llm_provider import LLMConfigError, create_llm
from idea_to_action.api.models import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    SubmitRequest,
    SubmitResponse,
)
from idea_to_action.pipeline import run_pipeline
from idea_to_action.schemas.input import InputType


def create_app() -> FastAPI:
    app = FastAPI(
        title="Idea-to-Action API",
        version="0.1.0",
        description="Convert raw notes into organized ideas, action plans, and tool actions.",
    )

    # --- Exception handlers for proper error responses ---

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc.errors()),
                "error_type": "validation_error",
            },
        )

    @app.exception_handler(LLMConfigError)
    async def llm_config_handler(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "detail": str(exc),
                "error_type": "llm_not_configured",
            },
        )

    # --- Routes ---

    @app.get("/health", response_model=HealthResponse)
    async def health():
        llm_available = True
        try:
            from idea_to_action.agent.llm_provider import get_default_provider
            get_default_provider()
        except LLMConfigError:
            llm_available = False

        return HealthResponse(
            status="ok",
            version="0.1.0",
            llm_available=llm_available,
        )

    @app.post("/submit", response_model=SubmitResponse)
    async def submit(request: SubmitRequest):
        llm = _create_llm_or_raise()

        result = run_pipeline(
            raw_text=request.raw_text,
            llm=llm,
            input_type=InputType(request.input_type),
            source="api",
        )

        return SubmitResponse(
            trace_id=result.trace_id,
            status="success" if not result.errors else "partial",
            input_text=request.raw_text,
            organized=result.organized.model_dump(mode="json") if result.organized else None,
            plan=result.plan.model_dump(mode="json") if result.plan else None,
            tool_actions=result.tool_actions.model_dump(mode="json") if result.tool_actions else None,
            errors=[
                ErrorDetail(step=e.step, message=e.message, error_type=e.error_type)
                for e in result.errors
            ],
            processed_at=datetime.now(UTC).isoformat(),
        )

    return app


def _create_llm_or_raise():
    """Create LLM instance, raising HTTP 503 if not configured."""
    try:
        return create_llm()
    except LLMConfigError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "detail": str(e),
                "error_type": "llm_not_configured",
            },
        )

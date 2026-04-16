from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None


class StepResult(BaseModel):
    tool_name: str
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CommandResponse(BaseModel):
    run_id: str
    status: str
    intent: str
    message: str
    missing: List[str] = []
    steps: List[StepResult] = []


class RunSummary(BaseModel):
    run_id: str
    command: str
    intent: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


class RunDetail(RunSummary):
    error: Optional[str] = None
    steps: List[StepResult] = []


# ── Chat (new SSE-based endpoint) ──────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None

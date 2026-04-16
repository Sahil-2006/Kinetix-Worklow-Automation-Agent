import json
import logging
from typing import Any, Dict

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .agents.orchestrator import react_loop
from .agents.planner import build_plan
from .auth.dependencies import get_current_user
from .auth.routes import init_auth_routes
from .core.config import CORS_ORIGINS, DATABASE_URL, OPENROUTER_API_KEY
from .executor import execute_plan
from .registry import build_registry
from .schemas import (
    ChatRequest,
    CommandRequest,
    CommandResponse,
    RunDetail,
    RunSummary,
    StepResult,
)
from .storage.db import TraceStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kinetix Workflow Automation Agent")

allow_origins = CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = TraceStore(DATABASE_URL)
registry = build_registry()

# ── Auth routes ────────────────────────────────────────────────
auth_router = init_auth_routes(store)
app.include_router(auth_router)


# ── Health (public) ────────────────────────────────────────────


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "llm_configured": bool(OPENROUTER_API_KEY),
        "tools": [t["name"] for t in registry.list()],
    }


# ── Tool listing (protected) ──────────────────────────────────


@app.get("/api/tools")
def list_tools(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    return registry.list()


# ── Chat endpoint with SSE streaming (protected) ──────────────


@app.post("/api/chat")
async def chat(
    payload: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """SSE-streaming chat endpoint.

    Accepts a natural-language message and streams the agent's
    ReAct loop as Server-Sent Events so the frontend can render
    thoughts, tool calls, and the final answer in real time.
    """

    user_id = current_user.get("sub")
    run_id, _ = store.create_run(payload.message, "llm_react", user_id=user_id)

    async def event_generator():
        try:
            async for event in react_loop(
                user_message=payload.message,
                registry=registry,
                store=store,
                run_id=run_id,
            ):
                yield {
                    "event": event["type"],
                    "data": json.dumps(event, default=str),
                }

            store.finish_run(run_id, "success")

        except Exception as exc:
            logger.exception("Chat stream error for run %s", run_id)
            store.finish_run(run_id, "failed", str(exc))
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": str(exc)}),
            }
            yield {
                "event": "done",
                "data": json.dumps({"type": "done"}),
            }

    return EventSourceResponse(event_generator())


# ── Legacy: synchronous command endpoint (protected) ──────────


@app.post("/api/command", response_model=CommandResponse)
def run_command(
    payload: CommandRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> CommandResponse:
    context = payload.context or {}
    plan = build_plan(payload.command, context)
    user_id = current_user.get("sub")
    run_id, _ = store.create_run(payload.command, plan.intent, user_id=user_id)

    if plan.intent == "unknown":
        store.finish_run(run_id, "failed", plan.message)
        return CommandResponse(
            run_id=run_id,
            status="failed",
            intent=plan.intent,
            message=plan.message,
            steps=[],
        )

    if plan.missing:
        store.finish_run(run_id, "needs_input", plan.message)
        return CommandResponse(
            run_id=run_id,
            status="needs_input",
            intent=plan.intent,
            message=plan.message,
            missing=plan.missing,
            steps=[],
        )

    try:
        step_results = execute_plan(
            plan, registry, store, run_id, payload.command, context
        )
        store.finish_run(run_id, "success")
        return CommandResponse(
            run_id=run_id,
            status="success",
            intent=plan.intent,
            message="Execution completed.",
            steps=[StepResult(**step) for step in step_results],
        )
    except Exception as exc:
        store.finish_run(run_id, "failed", str(exc))
        return CommandResponse(
            run_id=run_id,
            status="failed",
            intent=plan.intent,
            message=str(exc),
            steps=[],
        )


# ── Run history (protected — users see only their own) ────────


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> list[RunSummary]:
    user_id = current_user.get("sub")
    role = current_user.get("role", "user")

    # Admins see all runs, users see only their own
    if role == "admin":
        runs = store.list_runs(limit=20)
    else:
        runs = store.list_runs_for_user(user_id, limit=20)

    return [
        RunSummary(
            run_id=row["id"],
            command=row["command"],
            intent=row["intent"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
        for row in runs
    ]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> RunDetail:
    run = store.get_run(run_id)
    if not run:
        return RunDetail(
            run_id=run_id,
            command="",
            intent="unknown",
            status="missing",
            created_at="",
            completed_at=None,
            error="Run not found.",
            steps=[],
        )
    steps = store.get_steps(run_id)
    return RunDetail(
        run_id=run["id"],
        command=run["command"],
        intent=run["intent"],
        status=run["status"],
        created_at=run["created_at"],
        completed_at=run["completed_at"],
        error=run["error"],
        steps=[StepResult(**step) for step in steps],
    )

"""ReAct Orchestrator — the brain of the Kinetix agent.

Implements the Reason → Act → Observe loop:
1. Send the user message + tool definitions to the LLM (OpenRouter).
2. If the LLM returns tool_calls → execute them securely on the backend.
3. Append tool results as observations and call the LLM again.
4. Repeat until the LLM produces a final text answer or max iterations hit.

Yields SSE-compatible event dicts that the FastAPI endpoint streams to the
frontend in real time.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..core.config import MAX_REACT_ITERATIONS
from ..core.llm_client import LLMClient, LLMResponse, llm_client
from ..registry import ToolRegistry
from ..security.pii import redact_payload, redact_text
from ..storage.db import TraceStore
from ..tools.base import ToolContext
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _sse_event(event_type: str, **kwargs) -> Dict[str, Any]:
    """Helper to build a structured SSE event payload."""
    return {"type": event_type, **kwargs}


async def react_loop(
    user_message: str,
    registry: ToolRegistry,
    store: TraceStore,
    run_id: str,
    client: Optional[LLMClient] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Async generator that drives the ReAct loop and yields SSE events.

    Event types emitted:
      - ``thought``      – LLM's reasoning text (if any alongside tool calls)
      - ``tool_start``   – a tool is about to execute
      - ``tool_result``  – a tool finished; includes output or error
      - ``answer``       – final human-readable response from the LLM
      - ``error``        – an unrecoverable error occurred
      - ``done``         – stream is finished
    """

    llm = client or llm_client

    # Build initial message history
    system_prompt = build_system_prompt()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tool_schemas = registry.get_tool_schemas()

    safe_message = redact_text(user_message) or ""
    yield _sse_event("thought", content=f'Understanding your request: "{safe_message}"')

    for iteration in range(MAX_REACT_ITERATIONS):
        # ── REASON: call the LLM ──────────────────────────────────
        llm_call_id = store.create_llm_call(run_id, messages, iteration)

        try:
            response: LLMResponse = await llm.chat(
                messages=messages,
                tools=tool_schemas,
            )
        except Exception as exc:
            store.finish_llm_call(llm_call_id, error=str(exc))
            yield _sse_event(
                "error", content=redact_text(f"LLM call failed: {exc}") or ""
            )
            yield _sse_event("done")
            return

        store.finish_llm_call(
            llm_call_id,
            response_content=response.content,
            tool_calls_count=len(response.tool_calls),
            model=response.model,
            usage=response.usage,
        )

        # ── If LLM returned plain text with no tool calls → final answer ──
        if response.has_content and not response.has_tool_calls:
            yield _sse_event("answer", content=redact_text(response.content) or "")
            yield _sse_event("done")
            return

        # ── LLM emitted reasoning text alongside tool calls ──
        if response.has_content and response.has_tool_calls:
            yield _sse_event("thought", content=redact_text(response.content) or "")

        # ── ACT: execute each tool call ───────────────────────────
        # Build the assistant message with tool_calls for the message history
        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response.content or "",
        }
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in response.tool_calls
        ]
        messages.append(assistant_msg)

        for tc in response.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            safe_args = redact_payload(tool_args, mask_payload=True)
            yield _sse_event(
                "tool_start",
                tool=tool_name,
                arguments=safe_args,
                iteration=iteration,
            )

            # Log step start
            step_id, _ = store.create_step(run_id, tool_name, tool_args)

            # Build context for tool execution
            tool_context = ToolContext(
                run_id=run_id,
                store=store,
                command=user_message,
                user_context={},
            )

            try:
                tool = registry.get(tool_name)
                output = tool.execute(tool_args, tool_context)
                store.finish_step(step_id, "success", output_payload=output)
                safe_output = redact_payload(output, mask_payload=True)

                yield _sse_event(
                    "tool_result",
                    tool=tool_name,
                    status="success",
                    output=safe_output,
                    iteration=iteration,
                )

                # OBSERVE: append tool result to message history
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(output, default=str),
                    }
                )

            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                store.finish_step(step_id, "failed", error=error_msg)

                yield _sse_event(
                    "tool_result",
                    tool=tool_name,
                    status="failed",
                    error=redact_text(error_msg) or "",
                    iteration=iteration,
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": error_msg}),
                    }
                )

        # Loop back to REASON with the new observations

    # Max iterations reached
    yield _sse_event(
        "answer",
        content=redact_text(
            "I've reached the maximum number of reasoning steps. Here's what I accomplished so far — please refine your request if you need more."
        )
        or "",
    )
    yield _sse_event("done")

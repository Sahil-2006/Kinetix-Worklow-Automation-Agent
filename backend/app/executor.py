from typing import Any, Dict, List

from .agents.planner import Plan
from .registry import ToolRegistry
from .security.pii import redact_payload
from .storage.db import TraceStore
from .tools.base import ToolContext


def _resolve_ref(ref: str, step_outputs: List[Dict[str, Any]]) -> Any:
    if ref.startswith("steps."):
        parts = ref.split(".")
        idx = int(parts[1])
        current = step_outputs[idx]
        for key in parts[2:]:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current
    if ref.startswith("last."):
        if not step_outputs:
            return None
        current = step_outputs[-1]
        for key in ref.split(".")[1:]:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current
    return None


def _resolve_params(value: Any, step_outputs: List[Dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_params(v, step_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_params(item, step_outputs) for item in value]
    if isinstance(value, str) and value.startswith("$ref:"):
        resolved = _resolve_ref(value[5:], step_outputs)
        if resolved is None:
            raise ValueError(f"Unable to resolve reference: {value}")
        return resolved
    return value


def execute_plan(
    plan: Plan,
    registry: ToolRegistry,
    store: TraceStore,
    run_id: str,
    command: str,
    user_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    step_outputs: List[Dict[str, Any]] = []
    step_results: List[Dict[str, Any]] = []
    context = ToolContext(
        run_id=run_id, store=store, command=command, user_context=user_context
    )

    for step in plan.steps:
        tool = registry.get(step.tool_name)
        resolved_params = _resolve_params(step.params, step_outputs)
        step_id, _ = store.create_step(run_id, tool.name, resolved_params)
        try:
            output = tool.execute(resolved_params, context)
            store.finish_step(step_id, "success", output_payload=output)
            step_outputs.append(output)
            safe_output = redact_payload(output, mask_payload=True)
            step_results.append(
                {"tool_name": tool.name, "status": "success", "output": safe_output}
            )
        except Exception as exc:  # pragma: no cover - surfacing runtime tool errors
            store.finish_step(step_id, "failed", error=str(exc))
            step_results.append(
                {"tool_name": tool.name, "status": "failed", "error": str(exc)}
            )
            raise

    return step_results

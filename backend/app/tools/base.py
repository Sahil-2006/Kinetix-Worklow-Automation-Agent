from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolContext:
    run_id: str
    store: Any
    command: str
    user_context: Dict[str, Any]


class Tool:
    """Base class for all tools.

    Subclasses must set ``name``, ``description``, and implement
    ``execute``.  They should also set ``parameters_schema`` to an
    OpenAI-compatible JSON Schema dict so the LLM knows how to call them.
    """

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        raise NotImplementedError

    @property
    def tool_schema(self) -> Dict[str, Any]:
        """Return the OpenAI-compatible function tool definition.

        This is exactly the shape expected by the ``tools`` array in
        POST /chat/completions – both OpenAI and OpenRouter.
        """
        schema: Dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema or {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
        return schema

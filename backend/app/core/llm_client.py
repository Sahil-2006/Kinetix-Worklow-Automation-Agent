"""Async client for the OpenRouter chat completions API.

All LLM calls funnel through this module so that API keys stay
server-side and never leak to the model or the frontend.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ToolCallFunction:
    name: str
    arguments: str  # raw JSON string


@dataclass
class ToolCall:
    id: str
    type: str  # "function"
    function: ToolCallFunction


@dataclass
class LLMResponse:
    """Normalised response from the OpenRouter API."""

    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def has_content(self) -> bool:
        return bool(self.content)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Thin async wrapper around OpenRouter /chat/completions."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or OPENROUTER_MODEL
        self.base_url = base_url or OPENROUTER_BASE_URL
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send a chat completion request and return a normalised response."""

        if not self.is_configured:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Add it to your .env file to enable LLM reasoning."
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kinetix.dev",
            "X-Title": "Kinetix Workflow Agent",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/chat/completions"
            logger.info("LLM request → %s  model=%s  msgs=%d", url, self.model, len(messages))

            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return self._parse(data)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(data: Dict[str, Any]) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content")
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: List[ToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    type=tc.get("type", "function"),
                    function=ToolCallFunction(
                        name=fn.get("name", ""),
                        arguments=fn.get("arguments", "{}"),
                    ),
                )
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            raw=data,
        )


# Singleton – import and reuse
llm_client = LLMClient()

from typing import Any, Dict, List

from .tools.base import Tool
from .tools.calendar import CalendarScheduleTool
from .tools.csv_analyzer import CsvAnalyzerTool
from .tools.email import EmailSendTool
from .tools.file_tools import FileReadTool, FileWriteTool
from .tools.report_summarizer import ReportSummarizerTool
from .tools.web_search import WebSearchTool


class ToolRegistry:
    def __init__(self, tools: List[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def list(self) -> List[dict]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the OpenAI-compatible ``tools`` array for LLM requests."""
        return [tool.tool_schema for tool in self._tools.values()]


def build_registry() -> ToolRegistry:
    tools = [
        FileReadTool(),
        FileWriteTool(),
        CsvAnalyzerTool(),
        ReportSummarizerTool(),
        CalendarScheduleTool(),
        EmailSendTool(),
        WebSearchTool(),
    ]
    return ToolRegistry(tools)

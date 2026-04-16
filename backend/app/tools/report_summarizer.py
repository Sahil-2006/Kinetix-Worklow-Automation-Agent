from typing import Any, Dict

from .base import Tool, ToolContext


class ReportSummarizerTool(Tool):
    name = "report_summarizer"
    description = "Summarize report text into key bullet points with word/line counts."
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The report text to summarize.",
            },
            "max_bullets": {
                "type": "integer",
                "description": "Maximum number of summary bullet points.",
                "default": 5,
            },
        },
        "required": ["text"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        text = params.get("text", "")
        max_bullets = int(params.get("max_bullets", 5))
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        summary_lines = lines[:max_bullets]
        if not summary_lines:
            summary = "No content to summarize."
        else:
            summary = "\n".join(f"- {line}" for line in summary_lines)
        word_count = len(text.split())
        return {"summary": summary, "line_count": len(lines), "word_count": word_count}

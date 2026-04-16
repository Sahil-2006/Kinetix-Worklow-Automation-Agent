from pathlib import Path
from typing import Any, Dict

from .base import Tool, ToolContext


class FileReadTool(Tool):
    name = "file_read"
    description = "Read a local text file and return its contents."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read.",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (truncates if exceeded).",
                "default": 4000,
            },
        },
        "required": ["path"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = Path(params["path"]).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        max_chars = int(params.get("max_chars", 4000))
        content = path.read_text(encoding="utf-8", errors="ignore")
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
        return {
            "path": str(path),
            "content": content,
            "chars": len(content),
            "truncated": truncated,
        }


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to a local file. Can write or append."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to write the file to.",
            },
            "content": {
                "type": "string",
                "description": "Content to write.",
            },
            "mode": {
                "type": "string",
                "description": "Write mode: 'write' (overwrite) or 'append'.",
                "default": "write",
                "enum": ["write", "append"],
            },
        },
        "required": ["path", "content"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = Path(params["path"]).expanduser()
        content = params.get("content", "")
        mode = params.get("mode", "write")
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return {"path": str(path), "bytes": len(content)}

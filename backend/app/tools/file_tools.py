from typing import Any, Dict

from .file_access import (
    MAX_TEXT_FILE_BYTES,
    MAX_WRITE_BYTES,
    display_data_path,
    ensure_file_size,
    resolve_data_path,
)
from .base import Tool, ToolContext


class FileReadTool(Tool):
    name = "file_read"
    description = "Read a local text file and return its contents."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path inside the configured data folder. Relative paths are recommended.",
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
        path = resolve_data_path(params.get("path"))
        if not path.is_file():
            raise FileNotFoundError("File not found in the configured data folder.")
        ensure_file_size(path, MAX_TEXT_FILE_BYTES)
        try:
            max_chars = int(params.get("max_chars", 4000))
        except (TypeError, ValueError) as exc:
            raise ValueError("max_chars must be an integer.") from exc
        if not 1 <= max_chars <= 20_000:
            raise ValueError("max_chars must be between 1 and 20000.")
        content = path.read_text(encoding="utf-8", errors="ignore")
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
        return {
            "path": display_data_path(path),
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
                "description": "File path inside the configured data folder. Relative paths are recommended.",
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
        path = resolve_data_path(params.get("path"))
        content = params.get("content", "")
        mode = params.get("mode", "write")
        if not isinstance(content, str):
            raise ValueError("File content must be text.")
        if mode not in {"write", "append"}:
            raise ValueError("mode must be either 'write' or 'append'.")
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > MAX_WRITE_BYTES:
            raise ValueError(f"File content exceeds the {MAX_WRITE_BYTES}-byte limit.")

        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            existing_size = path.stat().st_size if path.exists() else 0
            if existing_size + content_bytes > MAX_WRITE_BYTES:
                raise ValueError(f"The resulting file would exceed the {MAX_WRITE_BYTES}-byte limit.")
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return {"path": display_data_path(path), "bytes": content_bytes}

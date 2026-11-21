"""Path and size limits shared by the agent's local-file tools."""

from pathlib import Path

from ..core.config import DATA_DIR

MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
MAX_CSV_FILE_BYTES = 10 * 1024 * 1024
MAX_WRITE_BYTES = 100 * 1024


def resolve_data_path(raw_path: str) -> Path:
    """Resolve a relative or absolute path while keeping it inside DATA_DIR."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("A non-empty file path is required.")

    data_root = DATA_DIR.expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = data_root / candidate

    resolved = candidate.resolve(strict=False)
    try:
        relative_path = resolved.relative_to(data_root)
    except ValueError as exc:
        raise PermissionError("File access is restricted to the configured data folder.") from exc

    if not relative_path.parts:
        raise ValueError("A file path inside the configured data folder is required.")
    if any(
        part.lower() == ".git" or part.lower() == ".env" or part.lower().startswith(".env.")
        for part in relative_path.parts
    ):
        raise PermissionError("Git internals and environment files are not available to agent tools.")
    if resolved.exists() and not resolved.is_file():
        raise IsADirectoryError("The selected path is not a file.")
    return resolved


def ensure_file_size(path: Path, max_bytes: int) -> int:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes}-byte limit.")
    return size


def display_data_path(path: Path) -> str:
    return path.relative_to(DATA_DIR.expanduser().resolve()).as_posix()

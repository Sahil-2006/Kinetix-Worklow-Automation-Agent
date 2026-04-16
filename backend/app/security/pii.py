from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from cryptography.fernet import Fernet, InvalidToken

from ..core.config import PII_ENCRYPTION_KEY

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
_NAME_RE = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")

_SENSITIVE_TEXT_KEYS = {
    "body",
    "content",
    "message",
    "message_body",
    "report_content",
    "summary",
    "text",
}

_EMAIL_KEYS = {
    "to",
    "email",
    "emails",
    "recipient",
    "recipients",
    "attendees",
    "target_email",
}

_fernet: Fernet | None = None
_generated_key: bytes | None = None


def _get_fernet() -> Fernet:
    global _fernet, _generated_key
    if _fernet is not None:
        return _fernet

    if PII_ENCRYPTION_KEY:
        key = PII_ENCRYPTION_KEY.encode("utf-8")
    else:
        _generated_key = Fernet.generate_key()
        key = _generated_key
        logger.warning(
            "PII_ENCRYPTION_KEY not set. Generated ephemeral key for this process."
        )

    _fernet = Fernet(key)
    return _fernet


def encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "":
        return ""
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "":
        return ""
    try:
        raw = _get_fernet().decrypt(value.encode("utf-8"))
        return raw.decode("utf-8")
    except InvalidToken:
        logger.warning("Failed to decrypt value. Returning placeholder.")
        return "[DECRYPTION_FAILED]"


def encrypt_json(payload: Any) -> str | None:
    if payload is None:
        return None
    return encrypt_text(json.dumps(payload, ensure_ascii=True, default=str))


def decrypt_json(value: str | None) -> Any:
    if value is None:
        return None
    raw = decrypt_text(value)
    if raw in (None, "", "[DECRYPTION_FAILED]"):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _mask_email(match: re.Match) -> str:
    return f"{match.group(1)}***{match.group(3)}"


def _mask_name(match: re.Match) -> str:
    return f"{match.group(1)} {match.group(2)[:1]}***"


def redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    if text == "":
        return ""
    redacted = _EMAIL_RE.sub(_mask_email, text)
    redacted = _NAME_RE.sub(_mask_name, redacted)
    return redacted


def _redact_list(values: List[Any], mask_payload: bool) -> List[Any]:
    return [redact_payload(item, mask_payload=mask_payload) for item in values]


def redact_payload(payload: Any, mask_payload: bool = False) -> Any:
    if isinstance(payload, dict):
        redacted: Dict[str, Any] = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if (
                mask_payload
                and key_lower in _SENSITIVE_TEXT_KEYS
                and isinstance(value, str)
            ):
                redacted[key] = f"[REDACTED:{len(value)} chars]"
                continue
            if key_lower in _EMAIL_KEYS:
                if isinstance(value, list):
                    redacted[key] = [redact_text(v) for v in value]
                    continue
                if isinstance(value, str):
                    redacted[key] = redact_text(value)
                    continue
            redacted[key] = redact_payload(value, mask_payload=mask_payload)
        return redacted

    if isinstance(payload, list):
        return _redact_list(payload, mask_payload)

    if isinstance(payload, str):
        return redact_text(payload)

    return payload

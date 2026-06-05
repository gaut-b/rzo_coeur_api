"""
Log sanitization utilities.

Provides a structlog processor and helper functions that redact sensitive
field values before they are written to any log sink.  Values for keys
matching SENSITIVE_FIELDS are replaced with ``[REDACTED]``, recursively
for nested dicts and list items.

The ``sanitize_body`` helper parses a raw HTTP request body and returns a
sanitized, log-safe representation (dict or string) ready to be passed as
a keyword argument to any structlog logger.
"""

import json
from typing import Any
from urllib.parse import parse_qs

# ---------------------------------------------------------------------------
# Sensitive field names (case-insensitive comparison applied at call sites)
# ---------------------------------------------------------------------------
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password2",
        "new_password",
        "old_password",
        "current_password",
        "token",
        "key",
        "secret",
        "api_key",
        "access",
        "refresh",
        "access_token",
        "refresh_token",
        "authorization",
        "email",
    }
)

REDACTED = "[REDACTED]"
MAX_BODY_LOG_SIZE = 4096


# ---------------------------------------------------------------------------
# Core sanitization helpers
# ---------------------------------------------------------------------------


def _is_sensitive_key(key: str) -> bool:
    """Return True when *key* should have its value redacted."""
    normalized = key.lower()
    if normalized in SENSITIVE_FIELDS:
        return True

    # Support common email key variants used by structured logs.
    return normalized.endswith("_email") or normalized in {
        "email_address",
    }


def _sanitize_value(key: str, value: Any) -> Any:
    """
    Redact *value* when *key* is sensitive; recurse into dicts and lists.

    Parameters:
        key (str): The field name associated with the value.
        value (Any): The value to inspect.

    Returns:
        Any: The original value, ``REDACTED``, or a sanitized copy.
    """
    if _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    return value


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Return a sanitized copy of *data* with sensitive field values redacted.

    The original dict is never mutated.  The function recurses into nested
    dicts and lists so that deeply nested credentials are also redacted.

    Parameters:
        data (dict): The input mapping to sanitize.

    Returns:
        dict: A new dict with sensitive values replaced by ``[REDACTED]``.
    """
    return {k: _sanitize_value(k, v) for k, v in data.items()}


def sanitize_json(data: Any) -> Any:
    """
    Sanitize a parsed JSON payload recursively.

    Supports dict and list roots so bulk payloads like
    ``[{"password": "..."}]`` are redacted as well.

    Parameters:
        data (Any): Parsed JSON payload.

    Returns:
        Any: Sanitized payload preserving the original structure.
    """
    if isinstance(data, dict):
        return sanitize_dict(data)
    if isinstance(data, list):
        return [_sanitize_value("", item) for item in data]
    return data


def sanitize_body(body: bytes, content_type: str) -> dict[str, Any] | str | None:
    """
    Parse and sanitize a raw HTTP request body for safe logging.

    Behaviour by content type:

    - ``application/json`` — parsed, recursively sanitized, then returned as
      a dict.  The serialised representation is truncated to
      ``MAX_BODY_LOG_SIZE`` characters when it exceeds that limit.
    - ``multipart/form-data`` — always returns ``"[multipart - file upload]"``
      to avoid logging binary data or large file contents.
    - Anything else — decoded as UTF-8 and truncated when necessary.

    Parameters:
        body (bytes): The raw request body bytes.
        content_type (str): The value of the ``Content-Type`` header.

    Returns:
        dict | str | None: A log-safe representation, or ``None`` for empty
        bodies.
    """
    if not body:
        return None

    ct = (content_type or "").lower()

    if "multipart/form-data" in ct:
        return "[multipart - file upload]"

    if "application/json" in ct:
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "[invalid JSON body]"

        sanitized: Any = sanitize_json(parsed)

        try:
            serialized = json.dumps(sanitized, ensure_ascii=False)
        except (TypeError, ValueError):
            return "[non-serializable body]"

        if len(serialized) > MAX_BODY_LOG_SIZE:
            return f"{serialized[:MAX_BODY_LOG_SIZE]}...[TRUNCATED]"

        return sanitized

    if "application/x-www-form-urlencoded" in ct:
        try:
            decoded_form = body.decode("utf-8", errors="replace")
        except Exception:
            return "[invalid form body]"

        # parse_qs always returns list values; flatten singletons for readability.
        parsed_form = parse_qs(decoded_form, keep_blank_values=True)
        normalized_form = {key: values[0] if len(values) == 1 else values for key, values in parsed_form.items()}
        sanitized_form = sanitize_dict(normalized_form)

        serialized_form = json.dumps(sanitized_form, ensure_ascii=False)
        if len(serialized_form) > MAX_BODY_LOG_SIZE:
            return f"{serialized_form[:MAX_BODY_LOG_SIZE]}...[TRUNCATED]"

        return sanitized_form

    # Fallback: plain text
    try:
        decoded = body.decode("utf-8", errors="replace")
    except Exception:
        return "[binary body]"

    if len(decoded) > MAX_BODY_LOG_SIZE:
        return f"{decoded[:MAX_BODY_LOG_SIZE]}...[TRUNCATED]"

    return decoded


# ---------------------------------------------------------------------------
# Structlog processor
# ---------------------------------------------------------------------------


def sanitize_structlog_processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Structlog processor that redacts sensitive top-level keys in *event_dict*.

    Placed in the processor chain, it ensures that any field accidentally
    passed as a keyword argument to a structlog call (e.g. ``logger.info(
    "login", password=raw_password)``) is masked before the entry reaches
    the renderer.

    Parameters:
        logger: The wrapped logger (unused, required by structlog API).
        method (str): The log method name (unused, required by structlog API).
        event_dict (dict): The mutable log event dictionary.

    Returns:
        dict: The event dict with sensitive values replaced by ``[REDACTED]``.
    """
    for key in list(event_dict.keys()):
        if _is_sensitive_key(key):
            event_dict[key] = REDACTED
    return event_dict

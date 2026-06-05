"""Request/response logging middleware.

Logs the sanitized request body as a dedicated ``request_body`` event, then
logs ``response_error`` for 4xx/5xx responses with sanitized error details.
This keeps the full request lifecycle visible in separate entries.
"""

import structlog

from config.log_sanitizer import sanitize_body, sanitize_dict

logger = structlog.get_logger(__name__)

_SKIP_PATH_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/favicon.ico",
    "/.well-known/",
)


class RequestBodyLoggingMiddleware:
    """
    Middleware that logs request bodies and error responses.

    Must be placed after ``django_structlog.middlewares.RequestMiddleware``
    in the ``MIDDLEWARE`` list so that ``request_id`` is already bound to
    the structlog context when the body log entry is emitted.
    """

    def __init__(self, get_response):
        """Store the next middleware/view callable."""
        self.get_response = get_response

    def __call__(self, request):
        """
        Emit a dedicated ``request_body`` event before view execution and
        emit ``response_error`` only for 4xx/5xx responses.

        Parameters:
            request: The incoming Django HTTP request.

        Returns:
            HttpResponse: The response from the next middleware or view.
        """
        should_log = not any(request.path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES)
        request_body = None
        if should_log:
            request_body = self._log_body(request)

        response = self.get_response(request)
        if should_log:
            self._log_response_error(request, response, request_body)
        return response

    def _log_body(self, request):
        """Log the sanitized request body and return its sanitized value."""
        content_type: str = request.content_type or ""
        normalized_content_type = content_type.lower()

        if "multipart/form-data" in normalized_content_type:
            body = "[multipart - file upload]"
            logger.info(
                "request_body",
                body=body,
                method=request.method,
                path=request.path,
            )
            return body

        try:
            body_bytes: bytes = request.body  # cached after first read
        except Exception:
            return None

        if not body_bytes:
            return None

        # Only log body content for structured formats where field-level
        # sanitization is supported. For other types, log metadata only.
        if (
            "application/json" not in normalized_content_type
            and "application/x-www-form-urlencoded" not in normalized_content_type
        ):
            body = "[body omitted: unsupported content type]"
            logger.info(
                "request_body",
                body=body,
                method=request.method,
                path=request.path,
                body_size=len(body_bytes),
                content_type=content_type,
            )
            return body

        body = sanitize_body(body_bytes, content_type)
        if body is not None:
            logger.info(
                "request_body",
                body=body,
                method=request.method,
                path=request.path,
            )
        return body

    def _sanitize_response_detail(self, detail):
        """Return a sanitized representation of response error payloads."""
        if isinstance(detail, dict):
            return sanitize_dict(detail)
        if isinstance(detail, list):
            return [self._sanitize_response_detail(item) for item in detail]
        return detail

    def _log_response_error(self, request, response, request_body) -> None:
        """Emit a structured log for 4xx/5xx responses with error details."""
        status_code = getattr(response, "status_code", None)
        if status_code is None or status_code < 400:
            return

        detail = None
        if hasattr(response, "data"):
            detail = self._sanitize_response_detail(response.data)

        event = "response_error"
        payload = {
            "method": request.method,
            "path": request.path,
            "status_code": status_code,
            "body": request_body,
            "detail": detail,
        }

        if status_code >= 500:
            logger.error(event, **payload)
        else:
            logger.warning(event, **payload)

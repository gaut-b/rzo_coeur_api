import structlog
from rest_framework.views import exception_handler as drf_exception_handler

logger = structlog.get_logger(__name__)


def exception_handler(exc, context):
    """
    Custom DRF exception handler that logs error detail and sets the
    appropriate log level (WARNING for 4xx, ERROR for 5xx).

    django-structlog already logs ``request_finished`` with the status code
    (always at INFO level) and ``request_failed`` for unhandled exceptions.
    This handler complements that by adding the response payload (``detail``)
    which is not available elsewhere, and by applying severity-aware log
    levels.  ``method`` and ``path`` are omitted here because they are already
    bound to the structlog context by ``RequestMiddleware`` via
    ``request_started``.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code

        if status_code >= 500:
            logger.error("api_error", status_code=status_code, detail=response.data)
        else:
            logger.warning("api_error", status_code=status_code, detail=response.data)
    else:
        # Unhandled exception: django-structlog will emit request_failed, but
        # we log here too so the exc_info is captured at ERROR level with our
        # structured context.
        logger.error("unhandled_exception", exc_info=exc)

    return response

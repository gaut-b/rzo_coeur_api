import logging

from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("api")


def exception_handler(exc, context):
    """
    Custom DRF exception handler that logs all 4xx/5xx responses with the
    request path, method, status code, and error detail so production issues
    are visible in the logs without needing to inspect client-side responses.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        request = context.get("request")
        method = getattr(request, "method", "?")
        path = getattr(request, "path", "?")
        status_code = response.status_code

        if status_code >= 500:
            logger.error(
                "%s %s → %s | %s",
                method,
                path,
                status_code,
                response.data,
            )
        else:
            logger.warning(
                "%s %s → %s | %s",
                method,
                path,
                status_code,
                response.data,
            )

    return response

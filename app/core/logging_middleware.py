import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        response = await call_next(request)

        duration = time.monotonic() - start
        logger.info(
            "%s %s -> %s (%.2fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

        return response

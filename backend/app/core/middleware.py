import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_413_CONTENT_TOO_LARGE

logger = logging.getLogger("fitora")

# Above the 10 MiB progress-photo cap so a legitimate upload is rejected by the
# photo validator (which can explain itself) rather than bluntly here, but low
# enough that an unbounded body never reaches application code.
MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024

# Swagger UI pulls its own JS/CSS from a CDN and renders in a frame-ish way, so
# the strict API policy below would break it. These paths only exist when
# APP_DEBUG is on, and never in production.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

# This API only ever returns JSON. Nothing should be loading resources from it,
# framing it, or executing anything it returns, so the policy denies everything
# rather than allow-listing.
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_STATIC_HEADERS = {
    # Never let a browser second-guess our Content-Type. A JSON response
    # sniffed as HTML is how a stored payload becomes stored XSS.
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # Don't leak API paths (which contain resource ids) to third-party sites.
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    # The API needs none of these; deny them rather than inherit page defaults.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the response headers from §59.

    HSTS is only sent when the request actually arrived over HTTPS. Sending it
    over plain HTTP is meaningless (a browser ignores it), and sending it in
    local development would pin `localhost` to HTTPS in the developer's browser
    for a year — a genuinely annoying thing to have to undo.
    """

    def __init__(self, app: object, *, hsts_max_age: int = 63072000) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = f"max-age={hsts_max_age}; includeSubDomains"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        for header, value in _STATIC_HEADERS.items():
            response.headers.setdefault(header, value)

        if request.url.path not in _DOCS_PATHS:
            response.headers.setdefault("Content-Security-Policy", _CSP)

        # `x-forwarded-proto` covers the normal deployment shape, where TLS is
        # terminated at a proxy in front of the app.
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if request.url.scheme == "https" or forwarded_proto == "https":
            response.headers.setdefault("Strict-Transport-Security", self._hsts)

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized request bodies before they reach application code.

    Only checks the declared Content-Length: a chunked request without one
    still reaches the endpoint, where the upload validator caps what it reads.
    This is a cheap first line, not the only one.
    """

    def __init__(self, app: object, *, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Invalid Content-Length."},
                )
            if declared > self._max_bytes:
                logger.warning(
                    "rejected oversized request to %s (%d bytes declared)",
                    request.url.path,
                    declared,
                )
                return JSONResponse(
                    status_code=HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Request body is too large."},
                )
        return await call_next(request)


__all__ = [
    "MAX_REQUEST_BODY_BYTES",
    "RequestSizeLimitMiddleware",
    "SecurityHeadersMiddleware",
]

"""HTTP hardening middleware (pure ASGI, so it also covers streaming bodies)."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import error_body

# JSON API responses never need to load anything: lock the browser down completely.
API_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
# Auth responses carry tokens: never cache them.
NO_STORE_PREFIX = b"/api/v1/auth"
DOCS_PATHS = ("/api/docs", "/api/openapi.json")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                # Swagger UI needs scripts/styles, so docs keep only the non-CSP headers.
                extra = [h for h in API_SECURITY_HEADERS
                         if not (path.startswith(DOCS_PATHS) and h[0] == b"content-security-policy")]
                headers += [h for h in extra if h[0] not in existing]
                if path.startswith(NO_STORE_PREFIX.decode()):
                    headers.append((b"cache-control", b"no-store"))
                if self.hsts:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Reject bodies over `max_bytes` with 413, whether declared (Content-Length) or streamed.

    The body is buffered here, before the app reads it: FastAPI turns any error raised while it reads
    a body into a generic 400, so the limit must be enforced outside the app. Fine for a JSON-only API
    with a small cap (no file uploads).
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for key, value in scope.get("headers", []):
            if key == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await _too_large(send)
                return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":  # client went away
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await _too_large(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()  # later calls: wait for disconnect, as the server would

        await self.app(scope, replay, send)


async def _too_large(send: Send) -> None:
    import json

    body = json.dumps(error_body("payload_too_large", "Request body too large")).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})

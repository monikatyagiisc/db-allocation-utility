import json
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("app.middleware")

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}
SKIP_BODY_PATHS = {"/api/databases/import", "/api/databases/export/excel"}
MAX_BODY_LOG_CHARS = 2000


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "<redacted>"
        else:
            sanitized[key] = value
    return sanitized


def _truncate(text: str, limit: int = MAX_BODY_LOG_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... <truncated {len(text) - limit} chars>"


def _format_body(raw: bytes, content_type: str | None) -> str | None:
    if not raw:
        return None
    if content_type and "application/json" in content_type:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                redacted = {
                    k: "<redacted>" if k.lower() in ("password", "hashed_password", "token", "access_token") else v
                    for k, v in parsed.items()
                }
                return _truncate(json.dumps(redacted, default=str))
            return _truncate(json.dumps(parsed, default=str))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    if content_type and ("multipart" in content_type or "octet-stream" in content_type):
        return f"<binary body {len(raw)} bytes>"
    try:
        return _truncate(raw.decode("utf-8", errors="replace"))
    except Exception:
        return f"<body {len(raw)} bytes>"


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()
        path = request.url.path
        skip_body = path in SKIP_BODY_PATHS or request.method in ("GET", "HEAD", "OPTIONS")

        request_body_log: str | None = None
        if not skip_body and settings.log_request_body:
            try:
                body = await request.body()

                async def receive() -> dict[str, Any]:
                    return {"type": "http.request", "body": body, "more_body": False}

                request = Request(request.scope, receive)
                request_body_log = _format_body(body, request.headers.get("content-type"))
            except Exception as exc:
                logger.warning("[%s] Failed to read request body: %s", request_id, exc)

        logger.info(
            "[%s] --> %s %s | client=%s | query=%s | headers=%s",
            request_id,
            request.method,
            path,
            request.client.host if request.client else "unknown",
            dict(request.query_params) if request.query_params else {},
            _sanitize_headers(dict(request.headers)),
        )
        if request_body_log:
            logger.debug("[%s] request body: %s", request_id, request_body_log)

        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "[%s] !!! unhandled error %s %s | duration=%.1fms | error=%s: %s",
                request_id,
                request.method,
                path,
                duration_ms,
                type(exc).__name__,
                exc,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        log_fn = logger.info if status < 400 else logger.warning if status < 500 else logger.error

        content_type = response.headers.get("content-type", "")
        content_length = response.headers.get("content-length", "?")
        response_detail = f"status={status} type={content_type} length={content_length}"

        log_fn(
            "[%s] <-- %s %s | %s | duration=%.1fms",
            request_id,
            request.method,
            path,
            response_detail,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

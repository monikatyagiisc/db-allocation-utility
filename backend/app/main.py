from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import get_logger, setup_logging
from app.middleware.logging import LoggingMiddleware
from app.routers import auth, databases

setup_logging()
logger = get_logger("app.main")


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    logger.info("Running database migrations...")
    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations complete")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting DB Allocation Utility API")
    try:
        run_migrations()
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
    yield
    logger.info("Shutting down DB Allocation Utility API")


app = FastAPI(title="DB Allocation Utility API", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

app.include_router(auth.router)
app.include_router(databases.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "HTTP %s %s | status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception on %s %s (request_id=%s): %s",
        request.method,
        request.url.path,
        request_id,
        exc,
    )
    content: dict = {"detail": "Internal server error. Check server logs for details."}
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=500, content=content)


@app.get("/api/health")
def health():
    logger.debug("Health check")
    return {"status": "ok"}

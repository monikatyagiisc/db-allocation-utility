import logging
import sys
from pathlib import Path

from app.config import settings

LOG_PREFIX = "[BE]"
LOG_FORMAT = f"%(asctime)s | {LOG_PREFIX} | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on reload
    root.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    if settings.log_file:
        log_path = Path(settings.log_file)
        if not log_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            log_path = project_root / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Quieter third-party loggers unless DEBUG
    if level <= logging.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger("app").info(
        "Logging initialized level=%s file=%s",
        settings.log_level,
        settings.log_file or "(console only)",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

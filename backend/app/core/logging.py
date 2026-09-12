import logging
import sys
from app.core.config import settings


class CustomFormatter(logging.Formatter):
    """Custom log formatter rendering timestamp | level | logger | message."""

    def format(self, record: logging.LogRecord) -> str:
        record.asctime = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        log_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging() -> logging.Logger:
    """Configures application-wide logging based on settings."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(CustomFormatter())
    root_logger.addHandler(console_handler)

    # Named logger for the app
    logger = logging.getLogger("cloudops")
    logger.setLevel(log_level)

    return logger


logger = setup_logging()

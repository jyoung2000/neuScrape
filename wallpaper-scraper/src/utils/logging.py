"""Logging configuration with rich formatting."""
import logging
import os
import sys

from rich.logging import RichHandler


def setup_logging(level: str = None) -> logging.Logger:
    """Configure and return the application logger."""
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    log_file = os.environ.get("LOG_FILE", "/data/logs/scraper.log")

    # Create log directory if needed
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("wallpaper-scraper")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # Rich console handler
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
    )
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_fmt = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # Can't write log file — console only
        logger.warning("Could not create log file at %s, using console only", log_file)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """Get a child logger."""
    base = logging.getLogger("wallpaper-scraper")
    if not base.handlers:
        setup_logging()
    if name:
        return base.getChild(name)
    return base

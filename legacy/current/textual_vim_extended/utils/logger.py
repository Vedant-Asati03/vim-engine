"""Project-wide logging helpers built on telelog."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from telelog import Logger, create_logger  # type: ignore

DEFAULT_LOGGER_NAME = "textual_vim_extended"


@lru_cache(maxsize=None)
def get_logger(name: str = DEFAULT_LOGGER_NAME) -> Logger:
    """Return a singleton Logger instance for the requested component."""

    return create_logger(name)


def log_kv(logger: Logger, level: str, message: str, **kv: Any) -> None:
    """Emit a structured log entry with additional key/value pairs."""

    payload = " | ".join([message] + [f"{key}={value}" for key, value in kv.items()])
    if level == "debug":
        logger.debug(payload)
    elif level == "warning":
        logger.warning(payload)
    elif level == "error":
        logger.error(payload)
    else:
        logger.info(payload)

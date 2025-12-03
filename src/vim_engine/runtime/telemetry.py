"""Telemetry services built directly on telelog.

This module exposes a narrow surface area for the rest of the engine:

``configure(...)`` -- override or preset the telelog configuration
``get_logger(name)`` -- fetch (and cache) a configured logger
``record_event(name, ...)`` -- emit structured events at a chosen level
``span(name, ...)`` -- context manager marrying profiling + component tracking
"""

from __future__ import annotations

import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, MutableMapping, Optional, Tuple, cast

import telelog  # type: ignore[import]

tl = cast(Any, telelog)

ENV_PREFIX = "VIM_ENGINE_"
DEFAULT_LOGGER_NAME = os.getenv(f"{ENV_PREFIX}LOGGER", "vim_engine")
DEFAULT_LOG_FILE = os.getenv(f"{ENV_PREFIX}LOG_FILE", "")
DEFAULT_CHART_DIR = os.getenv(f"{ENV_PREFIX}CHART_DIR", "./.telemetry")

_LOGGER_CACHE: MutableMapping[str, Any] = {}
_ACTIVE_CONFIG: Optional[Any] = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(f"{ENV_PREFIX}{name}", default)


def _env_flag(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return repr(value) if isinstance(value, (dict, list, tuple, set)) else str(value)


def _format_pairs(data: Dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(key), _stringify(value)) for key, value in data.items()]


def _resolve_level() -> str:
    return (_env("LOG_LEVEL") or "INFO").upper()


def _apply_engine_overrides(config: Any) -> Any:
    """Ensure profiling stays enabled per wiki guidance."""

    config.with_profiling(True)
    return config


def _build_preset_config(preset: str) -> Any:
    config = tl.Config()
    key = preset.lower()

    if key == "development":
        config.with_min_level("DEBUG")
        config.with_console_output(True)
        config.with_colored_output(True)
        config.with_json_format(False)
    elif key == "production":
        config.with_min_level("INFO")
        config.with_console_output(False)
        log_path = _env("LOG_FILE", DEFAULT_LOG_FILE) or "vim_engine.log"
        config.with_file_output(log_path)
        config.with_buffering(True)
    elif key in {"performance", "performance_analysis"}:
        config.with_min_level("DEBUG")
        config.with_console_output(False)
        config.with_buffering(True)
        config.with_json_format(True)
        log_path = _env("LOG_FILE", DEFAULT_LOG_FILE) or "vim_engine-performance.log"
        config.with_file_output(log_path)
    else:
        raise ValueError(f"Unknown preset '{preset}'.")

    return _apply_engine_overrides(config)


def _build_default_config() -> Any:
    config = tl.Config()
    config.with_min_level(_resolve_level())

    if not _env_flag("DISABLE_CONSOLE", False):
        config.with_console_output(True)
        config.with_colored_output(not _env_flag("NO_COLOR", False))
    else:
        config.with_console_output(False)

    if _env_flag("LOG_JSON", False):
        config.with_json_format(True)

    log_file = _env("LOG_FILE") or DEFAULT_LOG_FILE
    if log_file:
        config.with_file_output(log_file)

    if _env_flag("LOG_BUFFERED", False):
        buffer_size = int(_env("LOG_BUFFER_SIZE") or "2048")
        config.with_buffering(True)
        config.with_buffer_size(buffer_size)

    return _apply_engine_overrides(config)


def configure(*, config: Optional[Any] = None, preset: Optional[str] = None) -> None:
    """Override the active telelog configuration.

    Parameters
    ----------
    config:
        Explicit ``tl.Config`` instance to adopt.
    preset:
        Named preset from the wiki (``"development"``, ``"production"``,
        ``"performance"``). ``config`` and ``preset`` are mutually exclusive.
    """

    global _ACTIVE_CONFIG
    if config and preset:
        raise ValueError("Provide either `config` or `preset`, not both.")

    if preset:
        config = _build_preset_config(preset)
    elif config is None:
        config = _build_default_config()

    _ACTIVE_CONFIG = _apply_engine_overrides(config)
    _LOGGER_CACHE.clear()


def _ensure_config() -> Any:
    global _ACTIVE_CONFIG
    if _ACTIVE_CONFIG is None:
        _ACTIVE_CONFIG = _build_default_config()
    return _ACTIVE_CONFIG


def get_logger(name: Optional[str] = None) -> Any:
    """Return a cached ``telelog.Logger`` configured for this engine."""

    logger_name = name or DEFAULT_LOGGER_NAME
    if logger_name not in _LOGGER_CACHE:
        _LOGGER_CACHE[logger_name] = tl.Logger.with_config(
            logger_name, _ensure_config()
        )
    return _LOGGER_CACHE[logger_name]


def _resolve_level_method(
    logger: Any, level: Any, *, expect_data: bool = False
) -> Tuple[Any, bool]:
    name = str(level).lower()
    if expect_data:
        with_attr = getattr(logger, f"{name}_with", None)
        if with_attr is not None:
            return with_attr, True

    attr = getattr(logger, name, None)
    if attr is None:
        raise ValueError(f"Unsupported log level '{level}'.")
    return attr, False


def record_event(
    name: str,
    *,
    level: str | Any = "info",
    data: Optional[Dict[str, Any]] = None,
    logger_name: Optional[str] = None,
) -> None:
    """Emit a structured event following the Telelog cookbook guidance."""

    log = get_logger(logger_name)
    payload = {"event": name, **(data or {})}
    method, accepts_data = _resolve_level_method(log, level, expect_data=True)
    message = f"event::{name}"
    if accepts_data:
        method(message, _format_pairs(payload))
    else:
        method(f"{message} {payload}")


@dataclass
class SpanHandle:
    """Handle returned from ``span`` for optional metadata updates."""

    logger: Any
    span_name: str
    component_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = _stringify(value)

    def _emit(
        self, level: str, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        payload = {"span": self.span_name, **self.metadata}
        if self.component_name:
            payload["component"] = self.component_name
        if extra:
            payload.update({key: _stringify(val) for key, val in extra.items()})

        method, accepts = _resolve_level_method(self.logger, level, expect_data=True)
        if accepts:
            method(message, _format_pairs(payload))
        else:
            method(f"{message} {payload}")

    def fail(self, reason: str) -> None:
        self._emit("error", "span::fail", {"reason": reason})

    def cancel(self, reason: str | None = None) -> None:
        extra = {"reason": reason} if reason else None
        self._emit("warning", "span::cancel", extra)


@contextmanager
def span(
    name: str,
    *,
    logger_name: Optional[str] = None,
    component: Optional[str | bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[SpanHandle]:
    """Profile a code block and (optionally) track it as a component.

    Parameters
    ----------
    name:
        Operation name passed to ``logger.profile``.
    logger_name:
        Target logger; defaults to the engine logger.
    component:
        If ``True`` use the same name as the profile; if a string, use it as the
        component identifier.
    metadata:
        Optional metadata that is written both as transient context and as
        component metadata when tracking is enabled.
    """

    log = get_logger(logger_name)
    component_name = None
    if component is True:
        component_name = name
    elif isinstance(component, str):
        component_name = component

    context_keys = []
    metadata_payload: Dict[str, Any] = {}
    if metadata:
        for key, value in metadata.items():
            serialized = _stringify(value)
            metadata_payload[key] = serialized
            log.add_context(key, serialized)
            context_keys.append(key)

    with ExitStack() as stack:
        if component_name:
            stack.enter_context(log.track_component(component_name))

        stack.enter_context(log.profile(name))
        handle = SpanHandle(
            logger=log,
            span_name=name,
            component_name=component_name,
            metadata=dict(metadata_payload),
        )

        try:
            yield handle
        except Exception as exc:
            handle.fail(str(exc))
            raise
        finally:
            for key in context_keys:
                log.remove_context(key)


# Initialize the module-level logger once the config is ready.
configure()
logger = get_logger()

__all__ = [
    "SpanHandle",
    "configure",
    "get_logger",
    "record_event",
    "span",
    "logger",
]

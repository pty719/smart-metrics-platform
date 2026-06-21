"""Structured JSON logging configuration using structlog.

Call ``setup_logging()`` once at application startup.
"""
from __future__ import annotations

import logging

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog to emit JSON-formatted structured logs.

    Args:
        log_level: Standard Python logging level string (e.g. "INFO", "DEBUG").
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

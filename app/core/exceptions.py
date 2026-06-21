"""Custom application exception hierarchy.

All domain exceptions inherit from AppException so that the global
FastAPI exception handler can catch them uniformly.
"""
from __future__ import annotations


class AppException(Exception):
    """Base application exception.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code to return to the client.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MetricNotFoundError(AppException):
    """Raised when a metric with the given name or id does not exist."""

    def __init__(self, name: str) -> None:
        super().__init__(f"指标 '{name}' 不存在", status_code=404)


class DuplicateMetricError(AppException):
    """Raised when trying to create a metric that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"指标 '{name}' 已存在", status_code=409)


class InvalidDataError(AppException):
    """Raised when the input data fails business-level validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class TaskNotFoundError(AppException):
    """Raised when a task with the given id does not exist."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"任务 '{task_id}' 不存在", status_code=404)

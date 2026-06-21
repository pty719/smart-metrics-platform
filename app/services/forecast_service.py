"""Forecast service — linear regression prediction with confidence intervals.

Implements simple linear regression for time-series forecasting.
The algorithm uses ordinary least squares (OLS) to fit a trend line,
then extrapolates forward and computes a basic confidence interval.

All heavy computation is delegated to a Celery worker; this module
provides the pure algorithm that the worker calls.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app.core.exceptions import InvalidDataError, MetricNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric
from app.models.task import Task, TaskStatus


# ---------------------------------------------------------------------------
# Pure algorithm functions (no DB access — easy to unit-test)
# ---------------------------------------------------------------------------


def linear_forecast(
    x: list[float],
    y: list[float],
    steps: int,
    conf_level: float = 0.95,
) -> dict:
    """Fit a simple linear regression and forecast *steps* points ahead.

    Uses OLS to estimate ``y = a + b*x``.  The confidence interval is
    computed as ``y_hat ± t * SE``, where ``SE`` is the standard error
    of the prediction and ``t`` is the t-distribution critical value
    (approximated via the normal distribution for simplicity).

    Args:
        x: Independent variable values (e.g. time indices).
        y: Dependent variable values (the observed data points).
        steps: Number of future points to forecast.
        conf_level: Confidence level for the interval (default 0.95).

    Returns:
        Dict with keys:

        - ``slope``: Fitted slope (``b``).
        - ``intercept``: Fitted intercept (``a``).
        - ``r_squared``: Coefficient of determination.
        - ``forecast_x``: List of future x values.
        - ``forecast_y``: List of predicted y values.
        - ``lower_bound``: List of lower confidence limits.
        - ``upper_bound``: List of upper confidence limits.
        - ``history_x``: The input ``x`` (echoed back).
        - ``history_y``: The input ``y`` (echoed back).

    Raises:
        InvalidDataError: When ``x`` and ``y`` have different lengths,
            or fewer than 2 points are provided.
    """
    if len(x) != len(y):
        raise InvalidDataError(
            f"x and y must have the same length, got {len(x)} and {len(y)}"
        )
    if len(x) < 2:
        raise InvalidDataError(
            "At least 2 data points are required for linear regression"
        )

    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    n = len(x_arr)

    # OLS: b = covariance(x,y) / variance(x)
    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)

    b = np.sum((x_arr - x_mean) * (y_arr - y_mean)) / np.sum((x_arr - x_mean) ** 2)
    a = y_mean - b * x_mean

    y_hat = a + b * x_arr
    residuals = y_arr - y_hat
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y_arr - y_mean) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot != 0 else 0.0

    # Standard error of regression ( Residual SE )
    sigma2 = ss_res / (n - 2) if n > 2 else 0.0
    sigma = math.sqrt(sigma2)

    # Forecast future x values (assume evenly spaced; extrapolate last step)
    step_size = (x_arr[-1] - x_arr[0]) / (n - 1) if n > 1 else 1.0
    last_x = x_arr[-1]
    forecast_x = [last_x + step_size * (i + 1) for i in range(steps)]

    forecast_y: list[float] = []
    lower_bound: list[float] = []
    upper_bound: list[float] = []

    # t-critical approximation (normal approx for large n; for small n
    # we use a rough approximation: t ≈ z + (z^3 + z)/(4*df) ...
    # here we just use 1.96 for 95% as a reasonable approx)
    import scipy.stats as stats

    try:
        t_crit = stats.t.ppf((1 + conf_level) / 2, df=n - 2)
    except Exception:  # pragma: no cover — fallback
        t_crit = 1.96

    for xf in forecast_x:
        yf = a + b * xf
        # SE of prediction = sigma * sqrt(1 + 1/n + (xf-x_mean)^2 / Sxx)
        Sxx = np.sum((x_arr - x_mean) ** 2)
        se_pred = sigma * math.sqrt(1.0 + 1.0 / n + (xf - x_mean) ** 2 / Sxx) if Sxx != 0 else sigma
        margin = t_crit * se_pred

        forecast_y.append(yf)
        lower_bound.append(yf - margin)
        upper_bound.append(yf + margin)

    return {
        "slope": round(float(b), 6),
        "intercept": round(float(a), 6),
        "r_squared": round(float(r_squared), 6),
        "forecast_x": [round(float(v), 6) for v in forecast_x],
        "forecast_y": [round(float(v), 6) for v in forecast_y],
        "lower_bound": [round(float(v), 6) for v in lower_bound],
        "upper_bound": [round(float(v), 6) for v in upper_bound],
        "history_x": [round(float(v), 6) for v in x],
        "history_y": [round(float(v), 6) for v in y],
        "steps": steps,
        "conf_level": conf_level,
    }


def build_forecast_result(
    metric_name: str,
    datapoints: list[Datapoint],
    steps: int,
    conf_level: float = 0.95,
) -> dict:
    """Run linear forecast on a list of ORM datapoints and return a
    serialisable result dict.

    Timestamps are converted to numeric indices (hours from first point)
    so that the regression is time-aware.

    Args:
        metric_name: Name of the metric (echoed into the result).
        datapoints: ``Datapoint`` ORM instances, sorted by timestamp asc.
        steps: Number of future points to forecast.
        conf_level: Confidence level (default 0.95).

    Returns:
        Dict suitable for storing as ``Task.result`` (JSON-serialisable).
    """
    if len(datapoints) < 2:
        raise InvalidDataError(
            f"Metric '{metric_name}' needs at least 2 data points for forecasting, "
            f"got {len(datapoints)}"
        )

    # Convert timestamps to numeric indices (hours since first point)
    t0 = datapoints[0].timestamp
    x: list[float] = []
    y: list[float] = []
    ts_labels: list[str] = []

    for dp in datapoints:
        # Hours from t0
        hours = (dp.timestamp - t0).total_seconds() / 3600.0
        x.append(hours)
        y.append(float(dp.value))
        ts_labels.append(dp.timestamp.isoformat())

    forecast = linear_forecast(x, y, steps, conf_level)

    # Generate human-readable forecast timestamps
    step_hours = x[-1] - x[0]  # total hours spanned
    avg_hours_per_point = step_hours / (len(x) - 1) if len(x) > 1 else 1.0
    last_ts = datapoints[-1].timestamp
    forecast_timestamps = [
        (last_ts + timedelta(hours=avg_hours_per_point * (i + 1))).isoformat()
        for i in range(steps)
    ]

    return {
        "metric_name": metric_name,
        "model": "linear_regression",
        "conf_level": conf_level,
        "slope": forecast["slope"],
        "intercept": forecast["intercept"],
        "r_squared": forecast["r_squared"],
        "history": [
            {"timestamp": ts_labels[i], "value": y[i]}
            for i in range(len(y))
        ],
        "forecast": [
            {
                "timestamp": forecast_timestamps[i],
                "value": forecast["forecast_y"][i],
                "lower_bound": forecast["lower_bound"][i],
                "upper_bound": forecast["upper_bound"][i],
            }
            for i in range(steps)
        ],
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# DB-facing helpers (called by the Celery task)
# ---------------------------------------------------------------------------


async def run_forecast_task(
    db_session_factory,
    task_id: str,
    metric_id: int,
    steps: int,
    conf_level: float = 0.95,
) -> dict:
    """Execute a forecast and persist the result to the ``Task`` DB record.

    This function is designed to be called **synchronously** from a Celery
    worker (which runs in a separate process and does NOT share the
    FastAPI event loop).  A new ``AsyncSession`` is created via
    *db_session_factory*.

    Args:
        db_session_factory: A callable that returns a new ``AsyncSession``.
        task_id: UUID of the ``Task`` row to update.
        metric_id: DB primary key of the ``Metric`` to forecast.
        steps: Number of future points to predict.
        conf_level: Confidence level for the interval.

    Returns:
        The forecast result dict (also written to ``Task.result``).

    Raises:
        MetricNotFoundError: If *metric_id* does not exist.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    async with db_session_factory() as db:  # type: ignore[call-arg]
        # Look up the task row
        task = await db.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Look up the metric
        metric = await db.get(Metric, metric_id)
        if metric is None:
            task.status = TaskStatus.FAILURE
            task.error_message = f"Metric with id={metric_id} not found"
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise MetricNotFoundError(f"id={metric_id}")

        # Fetch datapoints
        from sqlalchemy import select

        rows = await db.scalars(
            select(Datapoint)
            .where(Datapoint.metric_id == metric_id)
            .order_by(Datapoint.timestamp.asc())
        )
        datapoints = rows.all()

        if len(datapoints) < 2:
            task.status = TaskStatus.FAILURE
            task.error_message = (
                f"Metric '{metric.name}' needs at least 2 data points, "
                f"got {len(datapoints)}"
            )
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise InvalidDataError(task.error_message)

        # Mark as started
        task.status = TaskStatus.STARTED
        task.started_at = datetime.now(timezone.utc)
        await db.flush()

        # Run forecast
        result = build_forecast_result(metric.name, datapoints, steps, conf_level)

        # Persist result
        task.status = TaskStatus.SUCCESS
        task.result = result
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()

    return result

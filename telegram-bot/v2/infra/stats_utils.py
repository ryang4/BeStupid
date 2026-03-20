"""Pure statistical functions for analytics."""

from __future__ import annotations


def pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
    """Compute Pearson correlation coefficient for paired data.

    Returns None if fewer than 3 pairs or zero variance.
    """
    if len(pairs) < 3:
        return None

    n = len(pairs)
    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]

    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    x_var = sum((x - x_mean) ** 2 for x in x_vals)
    y_var = sum((y - y_mean) ** 2 for y in y_vals)

    denominator = (x_var * y_var) ** 0.5
    if denominator == 0:
        return None

    return round(numerator / denominator, 3)


def compute_linear_trend(
    data_points: list[tuple[int, float]],
) -> dict:
    """Compute linear regression on (x, y) data points.

    Args:
        data_points: list of (day_index, value) tuples

    Returns:
        {"slope": float, "intercept": float, "r_squared": float} or empty dict if insufficient data
    """
    if len(data_points) < 3:
        return {}

    n = len(data_points)
    x_vals = [p[0] for p in data_points]
    y_vals = [p[1] for p in data_points]

    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n

    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in data_points)
    ss_xx = sum((x - x_mean) ** 2 for x in x_vals)
    ss_yy = sum((y - y_mean) ** 2 for y in y_vals)

    if ss_xx == 0:
        return {}

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy != 0 else 0.0

    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 2),
        "r_squared": round(r_squared, 3),
    }


def compute_streak(statuses: list[bool]) -> dict:
    """Compute current and longest streak from a list of daily booleans (most recent first).

    Returns {"current": int, "longest": int, "direction": "positive"|"negative"|"none"}
    """
    if not statuses:
        return {"current": 0, "longest": 0, "direction": "none"}

    current = 0
    direction = "positive" if statuses[0] else "negative"
    for s in statuses:
        if (direction == "positive" and s) or (direction == "negative" and not s):
            current += 1
        else:
            break

    longest = 0
    temp = 0
    for s in reversed(statuses):
        if s:
            temp += 1
            longest = max(longest, temp)
        else:
            temp = 0

    return {
        "current": current if direction == "positive" else -current,
        "longest": longest,
        "direction": direction,
    }

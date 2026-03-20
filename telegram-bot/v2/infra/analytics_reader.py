"""
Analytical query methods for the BeStupid assistant.

Reads from SQLiteStateStore via composition. All methods return structured dicts
with provenance metadata for traceability.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from v2.infra.sqlite_state_store import SQLiteStateStore, _safe_float
from v2.infra.stats_utils import compute_linear_trend, compute_streak, pearson_correlation

# SQLite authorizer action codes
SQLITE_READ = 20
SQLITE_SELECT = 21
SQLITE_FUNCTION = 31
SQLITE_PRAGMA = 19

SQLITE_OK = 0
SQLITE_DENY = 1

SAFE_FUNCTIONS = {
    "abs", "avg", "count", "group_concat", "hex", "ifnull",
    "iif", "instr", "length", "like", "lower", "ltrim", "max",
    "min", "nullif", "printf", "quote", "replace", "round",
    "rtrim", "substr", "sum", "total", "trim", "typeof",
    "unicode", "upper", "zeroblob", "coalesce", "date", "time",
    "datetime", "julianday", "strftime", "json", "json_extract",
    "json_array_length",
}

SAFE_PRAGMAS = {"table_info", "table_list", "database_list"}

ROW_LIMIT = 200
CHAR_LIMIT = 8000
QUERY_TIMEOUT_SECONDS = 5


def _readonly_authorizer(action_code, arg1, arg2, db_name, trigger_name):
    """SQLite authorizer that only allows read operations."""
    if action_code in (SQLITE_READ, SQLITE_SELECT):
        return SQLITE_OK
    if action_code == SQLITE_FUNCTION:
        return SQLITE_OK if arg2 and arg2.lower() in SAFE_FUNCTIONS else SQLITE_DENY
    if action_code == SQLITE_PRAGMA:
        return SQLITE_OK if arg1 and arg1.lower() in SAFE_PRAGMAS else SQLITE_DENY
    return SQLITE_DENY


class AnalyticsReader:
    """All analytical query methods. Uses SQLiteStateStore via composition."""

    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store

    # ── run_query: read-only SQL tool ──

    def run_query(self, db_name: str, sql: str) -> dict[str, Any]:
        """Execute a read-only SQL query against a whitelisted database."""
        DB_PATHS: dict[str, Path] = {
            "state": self._store.db_path,
        }
        # Add brain.db if it exists
        brain_path = self._store.db_path.parent.parent / "memory" / "brain.db"
        if brain_path.exists():
            DB_PATHS["brain"] = brain_path

        if db_name not in DB_PATHS:
            return {"error": f"Unknown database: {db_name}. Available: {', '.join(DB_PATHS)}"}

        db_path = DB_PATHS[db_name]
        if not db_path.exists():
            return {"error": f"Database file not found: {db_name}"}

        # Open read-only connection
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.set_authorizer(_readonly_authorizer)

        # Set up timeout via progress handler
        start_time = time.monotonic()

        def _timeout_check():
            if time.monotonic() - start_time > QUERY_TIMEOUT_SECONDS:
                return 1  # Non-zero cancels the query
            return 0

        conn.set_progress_handler(_timeout_check, 1000)

        try:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = []
            for row in cursor:
                if len(rows) >= ROW_LIMIT:
                    break
                row_data = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    # BLOB handling
                    if isinstance(val, bytes):
                        val = f"<BLOB {len(val)} bytes>"
                    row_data[col] = val
                rows.append(row_data)

            result_text = str({"columns": columns, "rows": rows})
            truncated = len(result_text) > CHAR_LIMIT

            return {
                "columns": columns,
                "rows": rows[:ROW_LIMIT],
                "row_count": len(rows),
                "truncated": truncated or len(rows) >= ROW_LIMIT,
                "provenance": {
                    "source_db": db_name,
                    "query": sql[:200],
                },
            }
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            if "interrupted" in error_msg.lower():
                return {"error": f"Query timed out after {QUERY_TIMEOUT_SECONDS}s"}
            if "not authorized" in error_msg.lower():
                return {"error": f"Query blocked by security policy: {error_msg}"}
            return {"error": f"SQL error: {error_msg}"}
        except Exception as e:
            return {"error": f"Query failed: {e}"}
        finally:
            conn.close()

    # ── metric_trend ──

    def metric_trend(self, chat_id: int, field: str, days: int = 30) -> dict[str, Any]:
        """Time series + linear trend for a metric field."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._store._connect() as conn:
            rows = conn.execute(
                """
                SELECT dc.local_date, dm.value
                FROM day_context dc
                JOIN day_metric dm ON dm.day_id = dc.day_id AND dm.field = ?
                WHERE dc.chat_id = ? AND dc.local_date >= ?
                ORDER BY dc.local_date
                """,
                (field, chat_id, cutoff),
            ).fetchall()

        data_points = []
        missing_days = 0
        for i, row in enumerate(rows):
            val = _safe_float(row["value"])
            if val is not None:
                data_points.append((i, val))
            else:
                missing_days += 1

        values = [p[1] for p in data_points]
        trend = compute_linear_trend(data_points) if len(data_points) >= 3 else {}

        date_range_start = rows[0]["local_date"] if rows else cutoff
        date_range_end = rows[-1]["local_date"] if rows else datetime.now().strftime("%Y-%m-%d")

        result: dict[str, Any] = {
            "field": field,
            "sample_size": len(data_points),
            "missing_days": missing_days,
        }
        if values:
            result["current"] = values[-1]
            result["min"] = round(min(values), 2)
            result["max"] = round(max(values), 2)
            result["mean"] = round(sum(values) / len(values), 2)
        if trend:
            result["trend"] = trend
            # Interpret direction
            if trend["slope"] > 0.01:
                result["direction"] = "increasing"
            elif trend["slope"] < -0.01:
                result["direction"] = "decreasing"
            else:
                result["direction"] = "stable"

        result["provenance"] = {
            "source_table": "day_metric JOIN day_context",
            "sample_size": len(data_points),
            "date_range": f"{date_range_start} to {date_range_end}",
            "nulls_excluded": missing_days,
            "missing_days": days - len(rows),
        }
        return result

    # ── habit_completion ──

    def habit_completion(self, chat_id: int, habit_name: str, days: int = 30) -> dict[str, Any]:
        """Completion rate and streak for a habit."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._store._connect() as conn:
            rows = conn.execute(
                """
                SELECT dc.local_date, hi.status
                FROM habit_instance hi
                JOIN habit_definition hd ON hd.habit_id = hi.habit_id
                JOIN day_context dc ON dc.day_id = hi.day_id
                WHERE dc.chat_id = ? AND LOWER(hd.name) = LOWER(?)
                  AND dc.local_date >= ?
                ORDER BY dc.local_date DESC
                """,
                (chat_id, habit_name, cutoff),
            ).fetchall()

        if not rows:
            return {
                "habit_name": habit_name,
                "error": f"No data found for habit '{habit_name}'",
                "provenance": {"source_table": "habit_instance", "sample_size": 0},
            }

        total = len(rows)
        done = sum(1 for r in rows if r["status"] == "done")
        statuses = [r["status"] == "done" for r in rows]
        streak = compute_streak(statuses)

        date_range_start = rows[-1]["local_date"]
        date_range_end = rows[0]["local_date"]

        return {
            "habit_name": habit_name,
            "completion_rate": round(done / total, 2) if total else 0,
            "done_count": done,
            "total_days": total,
            "current_streak": streak["current"],
            "longest_streak": streak["longest"],
            "provenance": {
                "source_table": "habit_instance JOIN day_context",
                "sample_size": total,
                "date_range": f"{date_range_start} to {date_range_end}",
                "nulls_excluded": 0,
                "missing_days": days - total,
            },
        }

    # ── nutrition_summary ──

    def nutrition_summary(self, chat_id: int, date: str | None = None, days: int = 7) -> dict[str, Any]:
        """Daily nutrition totals from food_entry macro columns."""
        with self._store._connect() as conn:
            if date:
                # Single day
                rows = conn.execute(
                    """
                    SELECT dc.local_date,
                           COALESCE(SUM(fe.calories_est), 0) AS cal,
                           COALESCE(SUM(fe.protein_g_est), 0) AS prot,
                           COALESCE(SUM(fe.carbs_g_est), 0) AS carbs,
                           COALESCE(SUM(fe.fat_g_est), 0) AS fat,
                           COALESCE(SUM(fe.fiber_g_est), 0) AS fiber,
                           COUNT(fe.food_id) AS items
                    FROM day_context dc
                    LEFT JOIN food_entry fe ON fe.day_id = dc.day_id AND fe.calories_est IS NOT NULL
                    WHERE dc.chat_id = ? AND dc.local_date = ?
                    GROUP BY dc.local_date
                    """,
                    (chat_id, date),
                ).fetchall()
            else:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
                rows = conn.execute(
                    """
                    SELECT dc.local_date,
                           COALESCE(SUM(fe.calories_est), 0) AS cal,
                           COALESCE(SUM(fe.protein_g_est), 0) AS prot,
                           COALESCE(SUM(fe.carbs_g_est), 0) AS carbs,
                           COALESCE(SUM(fe.fat_g_est), 0) AS fat,
                           COALESCE(SUM(fe.fiber_g_est), 0) AS fiber,
                           COUNT(fe.food_id) AS items
                    FROM day_context dc
                    LEFT JOIN food_entry fe ON fe.day_id = dc.day_id AND fe.calories_est IS NOT NULL
                    WHERE dc.chat_id = ? AND dc.local_date >= ?
                    GROUP BY dc.local_date
                    ORDER BY dc.local_date DESC
                    """,
                    (chat_id, cutoff),
                ).fetchall()

        daily = []
        for r in rows:
            daily.append({
                "date": r["local_date"],
                "calories": r["cal"],
                "protein_g": r["prot"],
                "carbs_g": r["carbs"],
                "fat_g": r["fat"],
                "fiber_g": r["fiber"],
                "items": r["items"],
            })

        days_with_data = sum(1 for d in daily if d["calories"] > 0)

        return {
            "daily": daily,
            "days_with_data": days_with_data,
            "provenance": {
                "source_table": "food_entry JOIN day_context",
                "sample_size": len(daily),
                "date_range": f"{daily[-1]['date'] if daily else 'none'} to {daily[0]['date'] if daily else 'none'}",
                "nulls_excluded": len(daily) - days_with_data,
                "missing_days": 0,
            },
        }

    # ── correlate ──

    def correlate(self, chat_id: int, field_a: str, field_b: str, days: int = 30) -> dict[str, Any]:
        """Pearson correlation between two metric fields."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._store._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.value AS val_a, b.value AS val_b, dc.local_date
                FROM day_context dc
                JOIN day_metric a ON a.day_id = dc.day_id AND a.field = ?
                JOIN day_metric b ON b.day_id = dc.day_id AND b.field = ?
                WHERE dc.chat_id = ? AND dc.local_date >= ?
                ORDER BY dc.local_date
                """,
                (field_a, field_b, chat_id, cutoff),
            ).fetchall()

        pairs = []
        skipped = 0
        for row in rows:
            a = _safe_float(row["val_a"])
            b = _safe_float(row["val_b"])
            if a is not None and b is not None:
                pairs.append((a, b))
            else:
                skipped += 1

        if len(pairs) < 7:
            return {
                "field_a": field_a,
                "field_b": field_b,
                "error": f"Insufficient paired data: {len(pairs)} points (need 7+)",
                "provenance": {
                    "source_table": "day_metric JOIN day_context",
                    "sample_size": len(pairs),
                },
            }

        r = pearson_correlation(pairs)
        interpretation = "no correlation"
        if r is not None:
            if r > 0.7:
                interpretation = "strong positive"
            elif r > 0.4:
                interpretation = "moderate positive"
            elif r > 0.1:
                interpretation = "weak positive"
            elif r > -0.1:
                interpretation = "no correlation"
            elif r > -0.4:
                interpretation = "weak negative"
            elif r > -0.7:
                interpretation = "moderate negative"
            else:
                interpretation = "strong negative"

        date_range_start = rows[0]["local_date"] if rows else ""
        date_range_end = rows[-1]["local_date"] if rows else ""

        return {
            "field_a": field_a,
            "field_b": field_b,
            "pearson_r": r,
            "interpretation": interpretation,
            "paired_data_points": len(pairs),
            "provenance": {
                "source_table": "day_metric JOIN day_context",
                "sample_size": len(pairs),
                "date_range": f"{date_range_start} to {date_range_end}",
                "nulls_excluded": skipped,
                "missing_days": days - len(rows),
            },
        }

    # ── get_computed_insights ──

    def get_computed_insights(self, chat_id: int) -> dict[str, Any]:
        """Compute aggregate insights: TDEE estimate, key correlations, habit streaks."""
        insights: list[dict[str, Any]] = []

        # 1. Weight trend (30 days)
        weight_trend = self.metric_trend(chat_id, "Weight", days=30)
        if weight_trend.get("sample_size", 0) >= 7:
            insights.append({
                "type": "weight_trend",
                "summary": (
                    f"Weight {weight_trend.get('direction', 'unknown')} over 30 days: "
                    f"{weight_trend.get('current', '?')} lbs "
                    f"(range {weight_trend.get('min', '?')}-{weight_trend.get('max', '?')})"
                ),
                "data": weight_trend,
            })
        else:
            insights.append({
                "type": "weight_trend",
                "summary": f"Insufficient weight data ({weight_trend.get('sample_size', 0)} of 14+ needed)",
            })

        # 2. Sleep → Mood correlation
        sleep_mood = self.correlate(chat_id, "Sleep", "Mood_AM", days=30)
        if sleep_mood.get("pearson_r") is not None:
            insights.append({
                "type": "sleep_mood_correlation",
                "summary": f"Sleep→Morning Mood: {sleep_mood['interpretation']} (r={sleep_mood['pearson_r']})",
                "data": sleep_mood,
            })

        # 3. TDEE estimate (requires weight + nutrition data)
        with self._store._connect() as conn:
            tdee_rows = conn.execute(
                """
                SELECT dc.local_date,
                       (SELECT dm.value FROM day_metric dm WHERE dm.day_id = dc.day_id AND dm.field = 'Weight') AS weight,
                       (SELECT COALESCE(SUM(fe.calories_est), 0) FROM food_entry fe WHERE fe.day_id = dc.day_id AND fe.calories_est IS NOT NULL) AS calories
                FROM day_context dc
                WHERE dc.chat_id = ?
                ORDER BY dc.local_date DESC
                LIMIT 30
                """,
                (chat_id,),
            ).fetchall()

        weight_cal_pairs = []
        for r in tdee_rows:
            w = _safe_float(r["weight"])
            c = r["calories"]
            if w and c and c > 0:
                weight_cal_pairs.append({"weight": w, "calories": c})

        if len(weight_cal_pairs) >= 14:
            avg_cal = sum(p["calories"] for p in weight_cal_pairs) / len(weight_cal_pairs)
            first_weight = weight_cal_pairs[-1]["weight"]
            last_weight = weight_cal_pairs[0]["weight"]
            weight_change = last_weight - first_weight
            # Rough TDEE: avg calories - (weight_change_lbs * 3500 / days)
            days_span = len(weight_cal_pairs)
            tdee_est = round(avg_cal - (weight_change * 3500 / days_span))
            insights.append({
                "type": "tdee_estimate",
                "summary": f"Estimated TDEE: ~{tdee_est} cal/day (based on {days_span} days of weight+calorie data)",
                "data": {
                    "tdee": tdee_est,
                    "avg_intake": round(avg_cal),
                    "weight_change_lbs": round(weight_change, 1),
                    "days": days_span,
                },
            })
        else:
            insights.append({
                "type": "tdee_estimate",
                "summary": f"Insufficient data for TDEE ({len(weight_cal_pairs)} days, need 14+)",
            })

        return {
            "insights": insights,
            "provenance": {
                "source_table": "day_metric, food_entry, habit_instance",
                "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        }

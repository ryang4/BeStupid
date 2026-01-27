"""
Garmin Connect Integration - Sync wearable data for recovery-aware planning.

Fetches:
- Sleep data (total, stages, score)
- Heart rate variability (HRV)
- Training readiness / Body Battery
- Training load and status
- Recent activities with details

Requires:
- pip install garminconnect
- GARMIN_EMAIL and GARMIN_PASSWORD environment variables

Usage:
    python garmin_sync.py              # Sync yesterday's data
    python garmin_sync.py --days 7     # Sync last 7 days
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional
import argparse

try:
    from garminconnect import Garmin
except ImportError:
    print("Error: garminconnect not installed. Run: pip install garminconnect")
    Garmin = None

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
GARMIN_DATA_FILE = os.path.join(PROJECT_ROOT, "data", "garmin_metrics.json")


def get_garmin_client() -> Optional[Garmin]:
    """
    Initialize and authenticate Garmin Connect client.

    Uses environment variables for credentials.
    Caches session token for faster subsequent calls.
    """
    if Garmin is None:
        return None

    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")

    if not email or not password:
        print("Error: GARMIN_EMAIL and GARMIN_PASSWORD environment variables required")
        return None

    try:
        # Check for cached session
        token_file = os.path.join(PROJECT_ROOT, ".garmin_session")

        client = Garmin(email, password)

        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    tokens = json.load(f)
                client.login(tokens)
                print("   Using cached Garmin session")
                return client
            except Exception:
                pass

        # Fresh login
        client.login()

        # Cache the session
        try:
            with open(token_file, 'w') as f:
                json.dump(client.session.cookies.get_dict(), f)
        except Exception:
            pass

        print("   Logged in to Garmin Connect")
        return client

    except Exception as e:
        print(f"Error connecting to Garmin: {e}")
        return None


def fetch_sleep_data(client: Garmin, date_str: str) -> dict:
    """
    Fetch sleep data for a specific date.

    Returns:
        dict with total_sleep, deep, light, rem, awake, score
    """
    result = {
        "total_hours": None,
        "deep_hours": None,
        "light_hours": None,
        "rem_hours": None,
        "awake_hours": None,
        "score": None,
        "start_time": None,
        "end_time": None
    }

    try:
        sleep_data = client.get_sleep_data(date_str)

        if sleep_data:
            daily = sleep_data.get("dailySleepDTO", {})

            # Convert milliseconds to hours
            def ms_to_hours(ms):
                return round(ms / (1000 * 60 * 60), 2) if ms else None

            result["total_hours"] = ms_to_hours(daily.get("sleepTimeSeconds", 0) * 1000)
            result["deep_hours"] = ms_to_hours(daily.get("deepSleepSeconds", 0) * 1000)
            result["light_hours"] = ms_to_hours(daily.get("lightSleepSeconds", 0) * 1000)
            result["rem_hours"] = ms_to_hours(daily.get("remSleepSeconds", 0) * 1000)
            result["awake_hours"] = ms_to_hours(daily.get("awakeSleepSeconds", 0) * 1000)
            result["score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
            result["start_time"] = daily.get("sleepStartTimestampLocal")
            result["end_time"] = daily.get("sleepEndTimestampLocal")

    except Exception as e:
        print(f"   Warning: Could not fetch sleep data: {e}")

    return result


def fetch_hrv_data(client: Garmin, date_str: str) -> dict:
    """
    Fetch Heart Rate Variability data.

    Returns:
        dict with overnight_avg, weekly_avg, status
    """
    result = {
        "overnight_avg": None,
        "weekly_avg": None,
        "status": None,  # BALANCED, UNBALANCED_LOW, UNBALANCED_HIGH
        "readings": []
    }

    try:
        hrv_data = client.get_hrv_data(date_str)

        if hrv_data:
            summary = hrv_data.get("hrvSummary", {})
            result["overnight_avg"] = summary.get("lastNight")
            result["weekly_avg"] = summary.get("weeklyAvg")
            result["status"] = summary.get("status")

            # Get individual readings if available
            readings = hrv_data.get("hrvValues", [])
            if readings:
                result["readings"] = [
                    {"time": r.get("readingTimeLocal"), "value": r.get("hrvValue")}
                    for r in readings[:10]  # Limit to 10 readings
                ]

    except Exception as e:
        print(f"   Warning: Could not fetch HRV data: {e}")

    return result


def fetch_body_battery(client: Garmin, date_str: str) -> dict:
    """
    Fetch Body Battery (energy) data.

    Returns:
        dict with start, end, min, max, charged, drained
    """
    result = {
        "start_level": None,
        "end_level": None,
        "min_level": None,
        "max_level": None,
        "charged": None,
        "drained": None
    }

    try:
        bb_data = client.get_body_battery(date_str)

        if bb_data:
            stats = bb_data.get("bodyBatteryStatDTO", {})
            result["start_level"] = stats.get("startingValue")
            result["end_level"] = stats.get("endingValue")
            result["min_level"] = stats.get("minValue")
            result["max_level"] = stats.get("maxValue")
            result["charged"] = stats.get("chargedValue")
            result["drained"] = stats.get("drainedValue")

    except Exception as e:
        print(f"   Warning: Could not fetch Body Battery data: {e}")

    return result


def fetch_training_status(client: Garmin, date_str: str) -> dict:
    """
    Fetch training readiness and load data.

    Returns:
        dict with readiness_score, load_7day, vo2max, status
    """
    result = {
        "readiness_score": None,
        "readiness_status": None,  # READY, SLIGHTLY_TIRED, TIRED, etc.
        "training_load_7day": None,
        "load_status": None,  # OPTIMAL, HIGH, LOW, etc.
        "vo2max_run": None,
        "vo2max_bike": None
    }

    try:
        # Training readiness
        readiness = client.get_training_readiness(date_str)
        if readiness:
            result["readiness_score"] = readiness.get("score")
            result["readiness_status"] = readiness.get("status")

        # Training status (includes load and VO2 max)
        status = client.get_training_status(date_str)
        if status:
            result["training_load_7day"] = status.get("sevenDaysLoad")
            result["load_status"] = status.get("trainingLoadBalance")
            result["vo2max_run"] = status.get("mostRecentVO2Max", {}).get("running")
            result["vo2max_bike"] = status.get("mostRecentVO2Max", {}).get("cycling")

    except Exception as e:
        print(f"   Warning: Could not fetch training status: {e}")

    return result


def fetch_activities(client: Garmin, date_str: str) -> list:
    """
    Fetch activities for a specific date.

    Returns:
        list of activity dicts with type, distance, duration, hr, etc.
    """
    activities = []

    try:
        # Get activities for the date range
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        start = date_obj.strftime("%Y-%m-%d")
        end = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")

        acts = client.get_activities_by_date(start, end)

        for act in acts:
            activity = {
                "type": act.get("activityType", {}).get("typeKey", "unknown"),
                "name": act.get("activityName"),
                "start_time": act.get("startTimeLocal"),
                "duration_minutes": round(act.get("duration", 0) / 60, 1),
                "distance_km": round(act.get("distance", 0) / 1000, 2) if act.get("distance") else None,
                "calories": act.get("calories"),
                "avg_hr": act.get("averageHR"),
                "max_hr": act.get("maxHR"),
                "training_effect_aerobic": act.get("aerobicTrainingEffect"),
                "training_effect_anaerobic": act.get("anaerobicTrainingEffect"),
                "avg_pace_min_km": None,
                "elevation_gain_m": act.get("elevationGain")
            }

            # Calculate pace for running activities
            if activity["distance_km"] and activity["duration_minutes"]:
                if activity["type"] in ("running", "trail_running", "treadmill_running"):
                    pace = activity["duration_minutes"] / activity["distance_km"]
                    activity["avg_pace_min_km"] = round(pace, 2)

            activities.append(activity)

    except Exception as e:
        print(f"   Warning: Could not fetch activities: {e}")

    return activities


def fetch_resting_hr(client: Garmin, date_str: str) -> Optional[int]:
    """Fetch resting heart rate for a date."""
    try:
        hr_data = client.get_heart_rates(date_str)
        if hr_data:
            return hr_data.get("restingHeartRate")
    except Exception:
        pass
    return None


def fetch_stress_data(client: Garmin, date_str: str) -> dict:
    """
    Fetch stress data for a date.

    Returns:
        dict with avg_stress, max_stress, rest_stress, low/med/high durations
    """
    result = {
        "avg_stress": None,
        "max_stress": None,
        "rest_stress": None,
        "low_duration_min": None,
        "medium_duration_min": None,
        "high_duration_min": None
    }

    try:
        stress = client.get_stress_data(date_str)
        if stress:
            result["avg_stress"] = stress.get("overallStressLevel")
            result["max_stress"] = stress.get("maxStressLevel")
            result["rest_stress"] = stress.get("restStressLevel")
            result["low_duration_min"] = round(stress.get("lowStressDuration", 0) / 60, 0)
            result["medium_duration_min"] = round(stress.get("mediumStressDuration", 0) / 60, 0)
            result["high_duration_min"] = round(stress.get("highStressDuration", 0) / 60, 0)
    except Exception:
        pass

    return result


def sync_garmin_day(client: Garmin, date_str: str) -> dict:
    """
    Sync all Garmin data for a single day.

    Returns:
        Complete daily Garmin metrics dict
    """
    print(f"   Syncing Garmin data for {date_str}...")

    return {
        "date": date_str,
        "synced_at": datetime.now().isoformat(),
        "sleep": fetch_sleep_data(client, date_str),
        "hrv": fetch_hrv_data(client, date_str),
        "body_battery": fetch_body_battery(client, date_str),
        "training": fetch_training_status(client, date_str),
        "stress": fetch_stress_data(client, date_str),
        "resting_hr": fetch_resting_hr(client, date_str),
        "activities": fetch_activities(client, date_str)
    }


def load_garmin_data() -> dict:
    """Load existing Garmin data file."""
    if os.path.exists(GARMIN_DATA_FILE):
        try:
            with open(GARMIN_DATA_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"version": "1.0", "entries": []}


def save_garmin_data(data: dict):
    """Save Garmin data file."""
    data_dir = os.path.dirname(GARMIN_DATA_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    data["last_updated"] = datetime.now().isoformat()

    with open(GARMIN_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_recovery_score(entry: dict) -> dict:
    """
    Calculate a composite recovery score from Garmin metrics.

    Uses HRV, sleep score, body battery, and training readiness.

    Returns:
        dict with score (0-100), status, and recommendations
    """
    scores = []
    factors = []
    recommendations = []

    # HRV contribution (0-100 normalized)
    hrv = entry.get("hrv", {})
    if hrv.get("overnight_avg") and hrv.get("weekly_avg"):
        hrv_ratio = hrv["overnight_avg"] / hrv["weekly_avg"]
        hrv_score = min(100, max(0, hrv_ratio * 100))
        scores.append(hrv_score * 0.3)  # 30% weight

        if hrv_ratio < 0.85:
            factors.append("HRV below baseline")
            recommendations.append("Consider lighter intensity today")
        elif hrv_ratio > 1.1:
            factors.append("HRV above baseline")

    # Sleep score contribution
    sleep = entry.get("sleep", {})
    if sleep.get("score"):
        scores.append(sleep["score"] * 0.25)  # 25% weight

        if sleep["score"] < 60:
            factors.append("Poor sleep quality")
            recommendations.append("Prioritize recovery - consider rest day")
        elif sleep["score"] < 75:
            factors.append("Moderate sleep quality")

    # Body Battery contribution
    bb = entry.get("body_battery", {})
    if bb.get("start_level"):
        scores.append(bb["start_level"] * 0.25)  # 25% weight

        if bb["start_level"] < 30:
            factors.append("Low energy reserves")
            recommendations.append("Avoid high-intensity training")
        elif bb["start_level"] > 70:
            factors.append("High energy reserves")

    # Training readiness contribution
    training = entry.get("training", {})
    if training.get("readiness_score"):
        scores.append(training["readiness_score"] * 0.2)  # 20% weight

        if training.get("readiness_status") == "TIRED":
            factors.append("Training fatigue detected")
            recommendations.append("Reduce training volume")

    # Calculate composite score
    if scores:
        composite = sum(scores) / (sum([0.3, 0.25, 0.25, 0.2][:len(scores)]))
    else:
        composite = None

    # Determine status
    if composite is None:
        status = "unknown"
    elif composite >= 80:
        status = "optimal"
    elif composite >= 60:
        status = "good"
    elif composite >= 40:
        status = "moderate"
    else:
        status = "low"

    return {
        "score": round(composite, 1) if composite else None,
        "status": status,
        "factors": factors,
        "recommendations": recommendations
    }


def sync_garmin(days: int = 1) -> bool:
    """
    Main sync function - fetches Garmin data and saves to JSON.

    Args:
        days: Number of days to sync (default: 1 = yesterday)

    Returns:
        bool: True if sync successful
    """
    print("Connecting to Garmin Connect...")
    client = get_garmin_client()

    if not client:
        return False

    data = load_garmin_data()
    existing_dates = {e["date"] for e in data.get("entries", [])}

    synced = 0
    for i in range(days):
        date = datetime.now() - timedelta(days=i+1)
        date_str = date.strftime("%Y-%m-%d")

        if date_str in existing_dates:
            print(f"   Skipping {date_str} (already synced)")
            continue

        try:
            entry = sync_garmin_day(client, date_str)
            entry["recovery"] = get_recovery_score(entry)
            data["entries"].append(entry)
            synced += 1
        except Exception as e:
            print(f"   Error syncing {date_str}: {e}")

    if synced > 0:
        # Sort entries by date
        data["entries"].sort(key=lambda x: x["date"])
        save_garmin_data(data)
        print(f"\nSynced {synced} day(s) to {GARMIN_DATA_FILE}")
    else:
        print("\nNo new data to sync")

    return True


def get_latest_recovery() -> Optional[dict]:
    """
    Get the most recent recovery data for use in daily briefing.

    Returns:
        dict with date, recovery score, and key metrics
    """
    data = load_garmin_data()

    if not data.get("entries"):
        return None

    latest = data["entries"][-1]

    return {
        "date": latest["date"],
        "recovery": latest.get("recovery", {}),
        "sleep_score": latest.get("sleep", {}).get("score"),
        "sleep_hours": latest.get("sleep", {}).get("total_hours"),
        "hrv": latest.get("hrv", {}).get("overnight_avg"),
        "hrv_status": latest.get("hrv", {}).get("status"),
        "body_battery": latest.get("body_battery", {}).get("start_level"),
        "resting_hr": latest.get("resting_hr"),
        "training_readiness": latest.get("training", {}).get("readiness_score")
    }


def get_weekly_trends() -> dict:
    """
    Calculate 7-day trends for key metrics.

    Returns:
        dict with averages and trends for HRV, sleep, recovery
    """
    data = load_garmin_data()
    entries = data.get("entries", [])[-7:]

    if len(entries) < 2:
        return {"insufficient_data": True}

    def avg(values):
        valid = [v for v in values if v is not None]
        return round(sum(valid) / len(valid), 1) if valid else None

    return {
        "days_analyzed": len(entries),
        "hrv_avg": avg([e.get("hrv", {}).get("overnight_avg") for e in entries]),
        "sleep_score_avg": avg([e.get("sleep", {}).get("score") for e in entries]),
        "sleep_hours_avg": avg([e.get("sleep", {}).get("total_hours") for e in entries]),
        "body_battery_avg": avg([e.get("body_battery", {}).get("start_level") for e in entries]),
        "recovery_score_avg": avg([e.get("recovery", {}).get("score") for e in entries]),
        "resting_hr_avg": avg([e.get("resting_hr") for e in entries]),
        "stress_avg": avg([e.get("stress", {}).get("avg_stress") for e in entries])
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Garmin Connect data")
    parser.add_argument("--days", type=int, default=1, help="Number of days to sync")
    args = parser.parse_args()

    sync_garmin(days=args.days)

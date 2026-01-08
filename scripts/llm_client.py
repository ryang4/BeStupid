"""
LLM client for model integration.
Supports Hugging Face Inference API and Ollama.
Shared helper for weekly_planner.py and scheduler.py
"""

import requests
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from scripts directory only
load_dotenv(Path(__file__).parent / ".env")

# API tokens and hosts - load from .env
HF_TOKEN = os.environ.get("HF_TOKEN")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")

# Backend selection: "huggingface" or "ollama"
LLM_BACKEND = os.environ.get("LLM_BACKEND", "huggingface" if HF_TOKEN else "ollama")

# Model configuration
HF_MODEL = os.environ.get("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")

# API URLs - Hugging Face uses unified router endpoint
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434/api/chat"


def call_llm(messages, format_json=False, prefer_backend=None):
    """
    Call LLM API with automatic fallback between backends.

    Tries primary backend first, then falls back to alternate backend if it fails.
    Primary backend is Hugging Face (if HF_TOKEN set), otherwise Ollama.

    Args:
        messages: List of message dicts with 'role' and 'content'
                  Example: [{"role": "user", "content": "Hello"}]
        format_json: If True, request JSON output format
        prefer_backend: Optional. "huggingface" or "ollama" to try first (defaults to LLM_BACKEND)

    Returns:
        str: Model's response content

    Raises:
        RuntimeError: If all backends fail
    """
    primary = prefer_backend or LLM_BACKEND

    # Determine backend order
    if primary == "huggingface" and HF_TOKEN:
        backends = [
            ("huggingface", _call_huggingface),
            ("ollama", _call_ollama)
        ]
    else:
        backends = [
            ("ollama", _call_ollama),
            ("huggingface", _call_huggingface)
        ]

    errors = []

    for backend_name, backend_func in backends:
        # Skip Hugging Face if no token
        if backend_name == "huggingface" and not HF_TOKEN:
            continue

        try:
            print(f"   → Trying {backend_name}...")
            result = backend_func(messages, format_json)
            print(f"   ✓ Success with {backend_name}")
            return result
        except (ConnectionError, RuntimeError) as e:
            error_msg = str(e).replace("❌ ", "")  # Clean error message
            errors.append(f"{backend_name}: {error_msg}")
            if len([b for b in backends if b[0] != backend_name]) > 0:
                print(f"   ✗ {backend_name} failed, trying fallback...")
            continue

    # All backends failed
    raise RuntimeError(
        "All LLM backends failed:\n" + "\n".join(f"  - {e}" for e in errors)
    )


def _call_huggingface(messages, format_json=False):
    """Call Hugging Face Inference API."""
    if not HF_TOKEN:
        raise RuntimeError(
            "❌ HF_TOKEN environment variable not set. "
            "Get your token at https://huggingface.co/settings/tokens"
        )

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": HF_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "stream": False
    }

    if format_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json=payload,
            timeout=300  # 5 min timeout for large models
        )
        response.raise_for_status()

        data = response.json()
        return data['choices'][0]['message']['content']

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"❌ Cannot connect to Hugging Face API. Check your internet connection."
        )
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get('error', e.response.text)
        except:
            error_detail = e.response.text
        raise RuntimeError(
            f"❌ Hugging Face API error: {e.response.status_code} - {error_detail}"
        )
    except KeyError as e:
        raise RuntimeError(
            f"❌ Unexpected response format from Hugging Face: {response.text}"
        )
    except Exception as e:
        raise RuntimeError(f"❌ Unexpected error calling Hugging Face: {str(e)}")


def _call_ollama(messages, format_json=False):
    """Call Ollama API with streaming to avoid timeouts (fallback option)."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True
    }

    if format_json:
        payload["format"] = "json"

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=(10, None),  # 10s connect, no read timeout
            stream=True
        )
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if 'message' in chunk and 'content' in chunk['message']:
                    full_response += chunk['message']['content']
                if chunk.get('done', False):
                    break

        return full_response

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"❌ Cannot connect to Ollama at {OLLAMA_URL}. "
            f"Consider using Hugging Face instead (set HF_TOKEN in .env)"
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"❌ Ollama API error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        raise RuntimeError(f"❌ Unexpected error calling Ollama: {str(e)}")


def generate_weekly_protocol(goals, last_protocol, last_week_logs, exercise_history=None):
    """
    Generate next week's training protocol.

    Args:
        goals: Content of ryan.md (str)
        last_protocol: Last week's protocol markdown (str or None)
        last_week_logs: List of dicts with log data from last week
                        [{"date": "2025-12-01", "content": "...", "stats": {...}}, ...]
        exercise_history: Dict with exercise history and summaries from weekly_planner.py
                          {"exercises": {...}, "summary": {...}}

    Returns:
        str: Complete markdown protocol for next week
    """

    # Calculate stats from last week
    if last_week_logs:
        total_compliance = sum(log.get('stats', {}).get('compliance', 0) for log in last_week_logs)
        avg_compliance = total_compliance / len(last_week_logs) if last_week_logs else 0

        total_sleep = sum(log.get('stats', {}).get('sleep_hours', 0) for log in last_week_logs)
        avg_sleep = total_sleep / len(last_week_logs) if last_week_logs else 0

        analysis = f"""
## Last Week's Performance Analysis

- **Days logged:** {len(last_week_logs)}
- **Average compliance:** {avg_compliance:.1f}%
- **Average sleep:** {avg_sleep:.1f} hours
- **Logs summary:**
{chr(10).join([f"  - {log['date']}: Compliance {log.get('stats', {}).get('compliance', 'N/A')}%, Sleep {log.get('stats', {}).get('sleep_hours', 'N/A')}hrs" for log in last_week_logs])}
"""
    else:
        analysis = "## First Week - No Historical Data\n\nGenerate baseline protocol based on profile only."

    # Format exercise history for prompt
    if exercise_history and exercise_history.get("summary"):
        exercise_lines = []
        for exercise, data in sorted(exercise_history["summary"].items()):
            last = data["last_workout"]
            exercise_lines.append(f"### {exercise.title()}")
            exercise_lines.append(f"- **Trend:** {data['trend'].replace('_', ' ').title()}")
            exercise_lines.append(f"- **Sessions tracked:** {data['sessions']}")
            exercise_lines.append(f"- **Last session:** {last['date']} - {last['sets']}x{last['reps']} @ {last['weight']} lbs")
            exercise_lines.append(f"- **Max weight achieved:** {data['max_weight']} lbs")

            # Add progression recommendation
            if data['trend'] == 'improving':
                exercise_lines.append("- **Recommendation:** Increase weight by 5 lbs or add 1-2 reps")
            elif data['trend'] == 'declining':
                exercise_lines.append("- **Recommendation:** Hold weight, focus on form and hitting all reps")
            else:
                exercise_lines.append("- **Recommendation:** Try adding 1 rep per set or 2.5-5 lbs")
            exercise_lines.append("")

        exercise_history_text = "\n".join(exercise_lines)
        exercise_section = f"""
# STRENGTH EXERCISE HISTORY (Last 4 Weeks)

{exercise_history_text}

## Progressive Overload Instructions
Based on the history above:
1. For exercises with "Improving" trend: Increase weight 2.5-5 lbs
2. For exercises with "Stable" trend: Add 1-2 reps or try small weight increase
3. For exercises with "Declining" trend: Reduce weight 5%, focus on form
4. Rotate accessory exercises every 2-3 weeks for variety
"""
    else:
        exercise_section = """
# STRENGTH EXERCISE HISTORY
No historical exercise data available. Use baseline weights from ryan.md profile.
"""

    prompt = f"""You are an elite triathlon coach and productivity advisor helping Ryan achieve top 0.01% performance.

# RYAN'S PROFILE AND GOALS
{goals}

# LAST WEEK'S PROTOCOL
{last_protocol if last_protocol else "No previous protocol - this is the first week."}

{analysis}

{exercise_section}

# YOUR TASK
Generate a complete weekly protocol for the upcoming week in EXACTLY this markdown format.
IMPORTANT: Do NOT wrap the output in code fences. Return raw markdown only.

---
title: "Protocol YYYY-WXX: [Phase Name]"
date: YYYY-MM-DD
week_number: WXX
tags: ["protocol"]
phase: "[Base Building / Build / Peak]"
focus: "[Primary training focus]"
target_compliance: XX%
---

## 📅 Weekly Schedule

| Day | Type | Workout |
|-----|------|---------|
| Monday | [Type] | [Specific workout details] |
| Tuesday | [Type] | [Specific workout details] |
| Wednesday | [Type] | [Specific workout details] |
| Thursday | [Type] | [Specific workout details] |
| Friday | [Type] | [Specific workout details] |
| Saturday | [Type] | [Specific workout details] |
| Sunday | [Type] | [Specific workout details] |

## 🎯 Training Goals
- [Goal 1]
- [Goal 2]
- [Goal 3]

## 🚀 Startup Goals
- [Startup goal 1]
- [Startup goal 2]

## 📊 Weekly Targets

**Cardio Volume:**
- Swim: [XXXm]
- Bike: [XX minutes]
- Run: [XX miles]

**Strength:**
- [Lift 1 target]
- [Lift 2 target]

**Startup:**
- [Startup metric]

**Recovery:**
- [Recovery metric]

## 📱 Content Strategy

**Theme:** [Weekly content theme]

| Platform | Status | Topic |
|----------|--------|-------|
| [Platform] | [Status] | [Topic] |

## 🤖 AI Rationale

[2-3 paragraphs explaining WHY this protocol makes sense given Ryan's current state, performance trends, and goals. Reference specific data from last week.]

## 🧬 Human Notes

[Placeholder for Ryan to add his own adjustments/notes]

CRITICAL RULES:
1. If compliance was >85% and sleep >7hrs avg → Increase volume 5-10%
2. If compliance was 70-85% → Hold volume steady
3. If compliance was <70% OR sleep <6.5hrs avg → Reduce volume 10-20%
4. Always include 2x strength sessions (maintain 300 DL, 225 squat)
5. Balance triathlon + startup work (6+ hrs deep work/week)
6. Saturday = brick workout + content creation
7. Sunday = long run day (clear schedule, good for endurance)
8. Monday = recovery/rest day always
9. HIGH INTENSITY CARDIO: Include exactly ONE high-intensity cardio session per week:
   - Running intervals: 6x400m @ 5K pace with 90s jog recovery, OR 4x800m @ 10K pace
   - Cycling intervals: 5x3min at threshold (RPE 8) with 2min easy spin
   - Schedule on Wednesday or Thursday (NOT on heavy strength days)
   - Alternate between running and cycling each week
10. EXERCISE VARIETY: Ensure workout variety compared to last week:
    - Rotate at least 2 accessory exercises (use variations: incline vs flat, dumbbell vs barbell)
    - Vary rep ranges: if last week was 3x8, try 4x6 or 3x10 this week
    - For cardio: if last week was steady-state, include intervals; if intervals, include a tempo run
    - REFERENCE THE LAST WEEK'S PROTOCOL ABOVE - do not copy it exactly
11. PROGRESSIVE OVERLOAD: Use the exercise history data to set specific targets:
    - Reference actual weights/reps from history, not just ryan.md defaults
    - Apply progression recommendations from the history section above
    - If no history for an exercise, use ryan.md baseline

Return ONLY the markdown protocol, no extra commentary."""

    messages = [{"role": "user", "content": prompt}]
    return call_llm(messages)


def generate_daily_briefing(goals, protocol, last_3_days, day_name):
    """
    Generate daily briefing, workout, and todos based on protocol and recent logs.

    Args:
        goals: Content of ryan.md (str)
        protocol: This week's full protocol markdown (str)
        last_3_days: List of last 3 daily logs with full content
        day_name: Today's day name (e.g., "Thursday")

    Returns:
        dict with keys:
            - workout_type: str (strength|swim|bike|run|brick|recovery)
            - planned_workout: str
            - briefing: dict with focus, tips, warnings
            - todos: list of strings
            - include_strength_log: bool
            - cardio_activities: list of strings (subset of ["swim", "bike", "run"])
    """

    # Extract yesterday's todos if they exist
    yesterday_todos = []
    if last_3_days:
        yesterday = last_3_days[-1]  # Most recent day
        if 'todos' in yesterday:
            yesterday_todos = [
                todo for todo in yesterday['todos']
                if todo.startswith('- [ ]')  # Incomplete items
            ]

    prompt = f"""You are Ryan's AI coach providing aggressive, actionable daily guidance.

# TODAY IS: {day_name}

# RYAN'S GOALS
{goals}

# THIS WEEK'S PROTOCOL (contains the schedule for each day)
{protocol}

# LAST 3 DAYS OF LOGS
{json.dumps(last_3_days, indent=2)}

# YOUR TASK
1. **Extract today's planned workout** from the weekly protocol schedule for {day_name}
2. **Determine workout type and which log sections are needed**
3. **Analyze the last 3 days** (especially yesterday) to adjust the plan if needed
4. **Generate specific, actionable todos**
5. **Generate a structured daily briefing** with focus areas, tips, and warnings

Return response as JSON with EXACTLY this structure:
{{
  "workout_type": "strength|swim|bike|run|brick|recovery",
  "planned_workout": "Full workout description from protocol",
  "briefing": {{
    "focus": "ONE primary thing to focus on today (1 sentence, be specific)",
    "tips": [
      "Actionable tip based on recent performance data",
      "Another specific tip or technique cue",
      "Recovery/nutrition tip if relevant"
    ],
    "warnings": ["Alert about sleep debt, missed workouts, or concerning trends (empty array if none)"]
  }},
  "todos": [
    "- [ ] Specific action item 1",
    "- [ ] Specific action item 2"
  ],
  "include_strength_log": true or false,
  "strength_exercises": [
    {
      "exercise": "Exercise Name",
      "sets": 3,
      "reps": 10,
      "weight": "100 lbs or bodyweight"
    }
  ],
  "cardio_activities": ["swim", "bike", "run"]
}}

CRITICAL RULES:

1. **workout_type**: Choose ONE of: strength, swim, bike, run, brick, recovery
   - brick = combination workout (e.g., bike + run)

2. **include_strength_log**:
   - true ONLY if today involves weightlifting (deadlifts, squats, etc.)
   - false for cardio-only or recovery days

3. **strength_exercises**:
   - If include_strength_log is true, extract EVERY exercise, set, rep, and weight from the protocol.
   - If the protocol says "3x7 @ 115", sets=3, reps=7, weight="115".
   - If weight is not specified, use "0" or "bodyweight".
   - If include_strength_log is false, return an empty array [].

4. **cardio_activities**: List ONLY activities happening today
   - Swim day → ["swim"]
   - Brick workout → ["bike", "run"]
   - Strength day → []
   - Recovery → []

4. **todos**: MUST follow these rules:
   - Generate ONLY ONE todo: "- [ ] Perform today's workout"
   - Do NOT generate any other todos - the user manages their own task list
   - All other tasks come from carrying forward yesterday's incomplete items (handled separately)

5. **briefing**: Must be a structured object with:
   - **focus**: ONE clear priority for today. Be aggressive and specific.
     ✅ "Lock in 6 hours sleep tonight - you're running a deficit"
     ✅ "Hit 305lb deadlift PR - your recovery metrics support it"
     ❌ "Try to have a good day"
   - **tips**: 2-4 actionable items. Reference specific data from logs.
     ✅ "Your HR was 145 avg on yesterday's easy run - keep today under 140"
     ✅ "You skipped stretching 3 days in a row - do 10 min post-workout TODAY"
     ❌ "Remember to stay hydrated"
   - **warnings**: Only include if there's a real concern. Empty array if things look good.
     ✅ "Sleep has been under 6.5hrs for 3 days - consider cutting volume 20%"
     ✅ "Missed 2 workouts this week - don't skip today"
"""

    messages = [{"role": "user", "content": prompt}]
    response = call_llm(messages, format_json=True)

    # Clean the response - LLMs often wrap JSON in markdown code fences
    cleaned = response.strip()

    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        # Remove closing fence
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    # Try to extract JSON object if there's extra text
    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if json_match:
        cleaned = json_match.group()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Print raw response for debugging
        print(f"\n⚠️  JSON parsing failed: {e}")
        print(f"📄 Raw LLM response:\n{response[:2000]}{'...' if len(response) > 2000 else ''}\n")
        # Fallback if JSON parsing fails
        return {
            "workout_type": "recovery",
            "planned_workout": f"Check protocol for {day_name}'s workout",
            "briefing": {
                "focus": "Execute today's protocol as planned",
                "tips": ["Review your weekly protocol for today's workout"],
                "warnings": ["Error generating AI briefing - check LLM output"]
            },
            "todos": yesterday_todos if yesterday_todos else ["- [ ] Review today's protocol"],
            "include_strength_log": False,
            "cardio_activities": []
        }


def estimate_macros(fuel_log_text):
    """
    Estimate calories and macros from a fuel log description.

    Args:
        fuel_log_text: Free-text description of food consumed

    Returns:
        dict with keys:
            - calories, protein_g, carbs_g, fat_g (summary totals)
            - line_items: array of individual food items with their macros
        Returns None if estimation fails
    """
    prompt = f"""Analyze this food log and estimate macronutrients for each food item AND the total.

Return ONLY a JSON object with this exact structure:
{{
  "total": {{
    "calories": <int>,
    "protein_g": <int>,
    "carbs_g": <int>,
    "fat_g": <int>
  }},
  "line_items": [
    {{
      "food": "<description of food item>",
      "time": "<time if mentioned, else null>",
      "calories": <int>,
      "protein_g": <int>,
      "carbs_g": <int>,
      "fat_g": <int>
    }}
  ]
}}

Be reasonable with estimates - use typical portion sizes if not specified.
Parse each line as a separate food item.

Food log:
{fuel_log_text}"""

    messages = [{"role": "user", "content": prompt}]

    try:
        response = call_llm(messages, format_json=True)

        # Clean the response - handle markdown code fences
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)

        # Extract JSON object
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            cleaned = json_match.group()

        data = json.loads(cleaned)

        # Extract totals
        total = data.get("total", {})
        line_items = data.get("line_items", [])

        return {
            "calories": int(total.get("calories", 0)),
            "protein_g": int(total.get("protein_g", total.get("protein", 0))),
            "carbs_g": int(total.get("carbs_g", total.get("carbs", 0))),
            "fat_g": int(total.get("fat_g", total.get("fat", 0))),
            "line_items": line_items
        }
    except (json.JSONDecodeError, RuntimeError) as e:
        print(f"⚠️  Macro estimation failed: {e}")
        return None

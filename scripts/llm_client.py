"""
LLM client for model integration.
Supports Hugging Face Inference API and Ollama.
Shared helper for weekly_planner.py and scheduler.py
"""

import requests
import json
import os
from pathlib import Path

# Load .env file if it exists
def _load_env():
    """Load environment variables from .env file."""
    env_paths = [
        Path(__file__).parent / ".env",  # scripts/.env
        Path(__file__).parent.parent / ".env",  # project root .env
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Remove quotes if present
                        value = value.strip().strip('"').strip("'")
                        os.environ.setdefault(key.strip(), value)
            break

_load_env()

# Configuration - set HF_TOKEN in .env or environment
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


def generate_weekly_protocol(goals, last_protocol, last_week_logs):
    """
    Generate next week's training protocol.

    Args:
        goals: Content of ryan.md (str)
        last_protocol: Last week's protocol markdown (str or None)
        last_week_logs: List of dicts with log data from last week
                        [{"date": "2025-12-01", "content": "...", "stats": {...}}, ...]

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

    prompt = f"""You are an elite triathlon coach and productivity advisor helping Ryan achieve top 0.01% performance.

# RYAN'S PROFILE AND GOALS
{goals}

# LAST WEEK'S PROTOCOL
{last_protocol if last_protocol else "No previous protocol - this is the first week."}

{analysis}

# YOUR TASK
Generate a complete weekly protocol for the upcoming week in EXACTLY this markdown format:

```markdown
---
title: "Protocol YYYY-WXX: [Phase Name]"
date: YYYY-MM-DD
week_number: WXX
tags: ["protocol"]

phase: "[Base Building / Build / Peak]"
focus: "[Primary training focus]"
target_compliance: XX%

schedule:
  monday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  tuesday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  wednesday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  thursday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  friday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  saturday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"
  sunday:
    type: "[Workout Type]"
    desc: "[Specific workout details]"

training_goals:
  - "[Goal 1]"
  - "[Goal 2]"
  - "[Goal 3]"

startup_goals:
  - "[Startup goal 1]"
  - "[Startup goal 2]"

content_strategy:
  theme: "[Weekly content theme]"
  posts:
    - platform: "[Platform]"
      status: "[Status]"
      topic: "[Topic]"

targets:
  cardio_volume:
    swim: "[XXXm]"
    bike: "[XX minutes]"
    run: "[XX miles]"
  strength:
    - "[Lift 1 target]"
    - "[Lift 2 target]"
  startup:
    - "[Startup metric]"
  recovery:
    - "[Recovery metric]"
---

## 🤖 AI Rationale

[2-3 paragraphs explaining WHY this protocol makes sense given Ryan's current state, performance trends, and goals. Reference specific data from last week.]

## 🧬 Human Notes

[Placeholder for Ryan to add his own adjustments/notes]
```

CRITICAL RULES:
1. If compliance was >85% and sleep >7hrs avg → Increase volume 5-10%
2. If compliance was 70-85% → Hold volume steady
3. If compliance was <70% OR sleep <6.5hrs avg → Reduce volume 10-20%
4. Always include 2x strength sessions (maintain 300 DL, 225 squat)
5. Balance triathlon + startup work (6+ hrs deep work/week)
6. Saturday = brick workout + content creation
7. Sunday = long run day (clear schedule, good for endurance)
8. Monday = recovery/rest day always

Return ONLY the markdown protocol, no extra commentary."""

    messages = [{"role": "user", "content": prompt}]
    return call_llm(messages)


def generate_daily_briefing(goals, protocol, last_3_days):
    """
    Generate daily briefing and todos based on recent logs.

    Args:
        goals: Content of ryan.md (str)
        protocol: This week's protocol (str)
        last_3_days: List of last 3 daily logs with full content

    Returns:
        dict: {"briefing": str, "todos": list}
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

# RYAN'S GOALS
{goals}

# THIS WEEK'S PROTOCOL
{protocol}

# LAST 3 DAYS OF LOGS
{json.dumps(last_3_days, indent=2)}

# YOUR TASK
Analyze the last 3 days (especially yesterday) and generate:

1. **Daily Briefing** (2-3 direct, actionable sentences):
   - Aggressively adjust today's workout based on yesterday's reality
   - If fatigued/poor sleep → reduce intensity significantly
   - If strong/recovered → stay the course or push slightly
   - Reference specific details from narratives

2. **Today's Todos** (5-7 items):
   - Carry forward incomplete items from yesterday
   - Add workout prep tasks
   - Add startup/content work based on goals
   - Prioritize based on narrative mentions
   - Use checkbox format: `- [ ] Task description`

Return response as JSON:
{{
  "briefing": "Your briefing text here",
  "todos": [
    "- [ ] Todo item 1",
    "- [ ] Todo item 2",
    "..."
  ]
}}

Be DIRECT and SPECIFIC. Examples:
✅ "Yesterday's brick left quads fatigued. Replace 4mi run with 30min walk + stretch."
❌ "Consider adjusting your workout if tired."
"""

    messages = [{"role": "user", "content": prompt}]
    response = call_llm(messages, format_json=True)

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {
            "briefing": "Error generating briefing - check LLM output",
            "todos": yesterday_todos if yesterday_todos else ["- [ ] Review today's protocol"]
        }

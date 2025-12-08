"""
Ollama API client for qwen model integration.
Shared helper for weekly_planner.py and scheduler.py
"""

import requests
import json

# Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:30b"
TIMEOUT = 180  # 3 minutes max for LLM response (larger model needs more time)

def call_ollama(messages, format_json=False):
    """
    Call Ollama API with qwen model.

    Args:
        messages: List of message dicts with 'role' and 'content'
                  Example: [{"role": "user", "content": "Hello"}]
        format_json: If True, request JSON output format

    Returns:
        str: Model's response content

    Raises:
        ConnectionError: If Ollama is not running
        TimeoutError: If request takes >TIMEOUT seconds
        RuntimeError: For other API errors
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }

    if format_json:
        payload["format"] = "json"

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()

        data = response.json()
        return data['message']['content']

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"❌ Cannot connect to Ollama at {OLLAMA_URL}. "
            f"Is Ollama running? Try: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"❌ Ollama request timed out after {TIMEOUT}s. "
            f"Model may be too slow or overloaded."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"❌ Ollama API error: {e.response.status_code} - {e.response.text}"
        )
    except KeyError:
        raise RuntimeError(
            f"❌ Unexpected response format from Ollama: {response.text}"
        )
    except Exception as e:
        raise RuntimeError(f"❌ Unexpected error calling Ollama: {str(e)}")


def generate_weekly_protocol(goals, last_protocol, last_week_logs):
    """
    Generate next week's training protocol using qwen.

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
7. Sunday = recovery day always

Return ONLY the markdown protocol, no extra commentary."""

    messages = [{"role": "user", "content": prompt}]
    return call_ollama(messages)


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
    response = call_ollama(messages, format_json=True)

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {
            "briefing": "Error generating briefing - check Ollama output",
            "todos": yesterday_todos if yesterday_todos else ["- [ ] Review today's protocol"]
        }

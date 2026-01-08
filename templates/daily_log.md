---
title: "{{ date }}: [{{ workout_type | capitalize }} Day]"
date: {{ date }}
tags: ["log"]
---

## Planned Workout
{{ planned_workout }}

## Daily Briefing

**Today's Focus:** {{ briefing.focus }}

{% if briefing.warnings %}
> **Alerts:**
{% for warning in briefing.warnings %}
> - {{ warning }}
{% endfor %}
{% endif %}

**Tips:**
{% for tip in briefing.tips %}
- {{ tip }}
{% endfor %}

## Today's Todos
{{ todos_markdown }}

## Daily Habits
{% for habit in habits %}
- [ ] {{ habit.name }}
  - *Setup: {{ habit.setup_action }}*
{% endfor %}

## Daily Stats
<!-- Enter values in the second column. Leave 0 if not applicable. -->

| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Weight (lbs)** | 0 | |
| **Sleep Hours** | 0 | |
| **Sleep Quality** | 0 | 1-10 |
| **Morning Mood** | 0  | 1-10  |
| **Bedtime Mood** |  0 |     |

{% if has_cardio %}
## Training Output

| Activity | Dist/Time | HR / Watts |
| :--- | :--- | :--- |
{% if 'swim' in cardio_activities %}
| **Swim (m)** | 0 | |
{% endif %}
{% if 'bike' in cardio_activities %}
| **Bike (mi)** | 0 | |
{% endif %}
{% if 'run' in cardio_activities %}
| **Run (mi)** | 0 | |
{% endif %}
{% endif %}

{% if include_strength_log %}
## Strength Log
<!-- Add rows as needed. Format: Sets | Reps | Weight -->

| Exercise | Sets | Reps | Weight (lbs) |
| :--- | :--- | :--- | :--- |
{% if strength_exercises %}
{% for ex in strength_exercises %}
| {{ ex.exercise }} | {{ ex.sets }} | {{ ex.reps }} | {{ ex.weight }} |
{% endfor %}
{% else %}
| Primary Lift | 0 | 0 | 0 |
| Accessory 1 | 0 | 0 | 0 |
{% endif %}
{% endif %}

## Fuel Log
*Describe your food here for the AI...*

## Daily Reflection
*What is one thing you learned today, one thing went well, and one thing that went poorly*

## Top 3 for Tomorrow
*Before bed, write the 3 most important things you need to accomplish tomorrow:*

1.
2.
3.
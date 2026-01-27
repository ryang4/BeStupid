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
{% endfor %}

## Quick Log
<!-- Tap after :: to enter values. Leave blank if not applicable. -->

Weight::
Sleep::
Sleep_Quality::
Mood_AM::
Mood_PM::
Energy::
Focus::
{% if has_cardio %}

## Training Output
<!-- Format: distance/time (e.g., 750m/33:39 or 4.5/45) -->
{% if 'swim' in cardio_activities %}
Swim::
{% endif %}
{% if 'bike' in cardio_activities %}
Bike::
{% endif %}
{% if 'run' in cardio_activities %}
Run::
{% endif %}
Avg_HR::
{% endif %}
{% if include_strength_log %}

## Strength Log
<!-- Format: Exercise: sets x reps @ weight -->
{% if strength_exercises %}
{% for ex in strength_exercises %}
{{ ex.exercise }}:: {{ ex.sets }}x{{ ex.reps }} @ {{ ex.weight }}
{% endfor %}
{% else %}
Primary_Lift::
Accessory_1::
Accessory_2::
{% endif %}
{% endif %}

## Fuel Log
<!-- List what you ate. Format: time - food description -->
calories_so_far:: 0
protein_so_far:: 0


## Top 3 for Tomorrow
<!-- Before bed, write your 3 most important tasks for tomorrow -->
1.
2.
3.

---
title: "{{ date }}: [{{ workout_type | capitalize }} Day]"
date: {{ date }}
tags: ["log"]
---

## Planned Workout
{{ planned_workout }}

## Daily Briefing
{{ briefing }}

## Today's Todos
{{ todos_markdown }}

## Daily Stats
<!-- Enter values in the second column. Leave 0 if not applicable. -->

| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Weight (lbs)** | 0 | |
| **Sleep Hours** | 0 | |
| **Sleep Quality** | 0 | 1-10 |
| **Morning Mood** |   | 1-10  |
| **Bedtime Mood** |  5  |     |

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
| Primary Lift | 0 | 0 | 0 |
| Accessory 1 | 0 | 0 | 0 |
{% endif %}

## Fuel Log
*Describe your food here for the AI...*

## Daily Reflection
*What is one thing you learned today, one thing went well, and one thing that went poorly*

## The Narrative
*Write about three things you DID today that are not recorded above. One interaction with a human and one place you went.*

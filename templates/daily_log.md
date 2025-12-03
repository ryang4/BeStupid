---
# ==========================================
# 📝 METADATA
# ==========================================
title: "Day {{date:DDD}}: [Headline]"
date: {{date:YYYY-MM-DD}}
tags: ["log", "human"]
vibe: "😐 Neutral"  # Options: 😤 Grinding, ⚡ Flow, 💀 Dead, 🧘 Recovery

# ==========================================
# 🎯 ACCOUNTABILITY (Auto-Filled by Script)
# ==========================================
# The Python Agent injects your orders here:
planned_workout:
  type: "{{plan_type}}"   # e.g. "Run"
  desc: "{{plan_desc}}"   # e.g. "5mi Aerobic (Zone 2)"

compliance: 100         # 0 = Skipped, 100 = Executed Perfectly
time_outside_min: 0     # Minutes (Sunlight/Grounding)

# ==========================================
# 🧬 TRAINING DATA (Actual Output)
# ==========================================
cardio:
  swim_m: 0
  bike_mi: 0
  run_mi: 0
  avg_hr: 0             # Average Heart Rate

strength:
  focus: "None"         # e.g. "Push", "Legs"
  exercises:            # Add items as needed. Leave 0 if not done.
    - name: "Primary Lift"
      sets: 0
      reps: 0
      weight_lbs: 0

# ==========================================
# 🥗 FUEL & RECOVERY
# ==========================================
sleep:
  hours: 0.0
  quality: 0            # 1-10 (Subjective or Oura)
  bed_time: "22:00"
  wake_time: "06:00"

diet:
  quality_score: 0      # 1-10 (Cleanliness)
  alcohol: false
  # 🤖 AI_FILLED_FIELDS (Leave these 0. The Agent calculates them from your text below)
  est_calories: 0
  est_protein_g: 0
  est_carbs_g: 0
  est_fat_g: 0
---

## 🏃 Session Notes
<!-- Context on the workout itself. Did you hit the planned targets? -->
*Plan was {{plan_desc}}. Execution was...*

## 🥗 Fuel Log
<!-- Describe food plainly. The AI reads this to estimate macros. -->
**Breakfast:** **Lunch:** **Dinner:** **Snacks:** ![[food_photo.jpg]]

---

## 📝 The Narrative
<!-- The "Iceberg Tip" - 2 sentences that appear on the homepage feed. -->
*...*
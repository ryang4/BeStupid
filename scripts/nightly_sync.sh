#!/bin/bash
cd /Users/ryang4/Projects/BeStupid

# 1. AI Analysis (Fills in Macros)
uv run --project scripts python scripts/local-agent.py

# 2. Database Sync (Markdown -> CSV) -- DISABLED: Not needed until weekly planner exists
# uv run --project scripts python scripts/sync_db.py

# 3. Dashboard Data (Aggregation for Charts)
uv run --project scripts python scripts/dashboard.py

# 4. Push to Cloud
git add .
git commit -m "🤖 Nightly Sync: Data & AI Analysis"
git push origin main
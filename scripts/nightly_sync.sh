#!/bin/bash
cd /home/YOUR_USER/my-n-equals-1-site

# 1. AI Analysis (Fills in Macros)
/usr/bin/python3 scripts/local_agent.py

# 2. Database Sync (Markdown -> CSV)
/usr/bin/python3 scripts/sync_db.py

# 3. Dashboard Data (Aggregation for Charts)
/usr/bin/python3 scripts/generate_dashboard.py

# 4. Push to Cloud
git add .
git commit -m "🤖 Nightly Sync: Data & AI Analysis"
git push origin main
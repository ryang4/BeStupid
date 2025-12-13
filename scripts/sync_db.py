import os
import csv
import frontmatter
from datetime import datetime

LOGS_DIR = "content/logs"
DB_FILE = "data/master_log.csv"
HEADERS = ["date", "vibe", "compliance", "weight", "sleep_hours", "diet_score", "calories", "swim_m", "bike_mi", "run_mi", "strength_vol"]

def sync_database():
    records = []
    for root, _, files in os.walk(LOGS_DIR):
        for f in files:
            if f.endswith(".md") and f != "_index.md":
                post = frontmatter.load(os.path.join(root, f))
                
                # Calculate Strength Vol
                vol = sum([x.get('sets',0)*x.get('reps',0)*x.get('weight_lbs',0) for x in post.get('strength', {}).get('exercises', [])])
                
                records.append({
                    "date": str(post.get('date')),
                    "vibe": post.get('vibe'),
                    "compliance": post.get('compliance'),
                    "weight": post.get('weight_lbs', 0), # <--- Captures weight
                    "sleep_hours": post.get('sleep', {}).get('hours'),
                    "diet_score": post.get('diet', {}).get('quality_score'),
                    "calories": post.get('diet', {}).get('est_calories'),
                    "swim_m": post.get('cardio', {}).get('swim_m'),
                    "bike_mi": post.get('cardio', {}).get('bike_mi'),
                    "run_mi": post.get('cardio', {}).get('run_mi'),
                    "strength_vol": vol
                })

    # Sort and Write
    records.sort(key=lambda x: x['date'])
    with open(DB_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(records)
    print("✅ Database Synced")

if __name__ == "__main__":
    sync_database()
import os
import json
import frontmatter
from datetime import datetime, timedelta

# CONFIGURATION
# ----------------------------------------------------------------
LOGS_DIR = "content/logs"
OUTPUT_FILE = "data/dashboard.json"

def get_buckets():
    """Create 4 weekly buckets (Current Week + Previous 3)"""
    buckets = []
    today = datetime.now()
    
    # Calculate start of current week (Monday)
    start_of_current_week = today - timedelta(days=today.weekday())
    
    for i in range(3, -1, -1):
        # Shift back i weeks
        week_start = start_of_current_week - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        
        buckets.append({
            "label": "Current" if i == 0 else f"W-{i}",
            "start": week_start.date(),
            "end": week_end.date(),
            # The Accumulators
            "data": {
                "swim": 0, "bike": 0, "run": 0, "strength_vol": 0,
                "compliance_sum": 0, "compliance_count": 0,
                "human_posts": 0, "ai_posts": 0
            }
        })
    return buckets

def scan_logs():
    buckets = get_buckets()
    latest_vibe = "System Offline"
    latest_protocol = "Unknown"

    # Walk through all day folders
    for root, dirs, files in os.walk(LOGS_DIR):
        for filename in files:
            if not filename.endswith(".md") or filename == "_index.md":
                continue
            
            filepath = os.path.join(root, filename)
            try:
                post = frontmatter.load(filepath)
                
                # Handle Date parsing
                p_date = post.get('date')
                if isinstance(p_date, str):
                    p_date = datetime.strptime(p_date, "%Y-%m-%d").date()
                elif isinstance(p_date, datetime):
                    p_date = p_date.date()

                # Grab latest vibe
                if p_date == datetime.now().date():
                    latest_vibe = post.get('vibe', latest_vibe)

                # Sort into Buckets
                for b in buckets:
                    if b['start'] <= p_date <= b['end']:
                        d = b['data']
                        
                        # 1. Cardio Volume
                        cardio = post.get('cardio', {})
                        d['swim'] += int(cardio.get('swim_m', 0))
                        d['bike'] += float(cardio.get('bike_mi', 0))
                        d['run'] += float(cardio.get('run_mi', 0))

                        # 2. Strength Volume (Sets * Reps * Weight)
                        strength = post.get('strength', {})
                        exercises = strength.get('exercises', [])
                        if exercises:
                            for ex in exercises:
                                vol = int(ex.get('sets', 0)) * int(ex.get('reps', 0)) * int(ex.get('weight_lbs', 0))
                                d['strength_vol'] += vol

                        # 3. Compliance (The Accountability Metric)
                        comp = post.get('compliance')
                        if comp is not None:
                            d['compliance_sum'] += int(comp)
                            d['compliance_count'] += 1
                        
                        # 4. Content Type
                        tags = post.get('tags', [])
                        if 'ai' in tags: d['ai_posts'] += 1
                        else: d['human_posts'] += 1

            except Exception as e:
                print(f"Skipping {filename}: {e}")

    return buckets, latest_vibe

def build_json():
    buckets, vibe = scan_logs()
    
    # Format for Chart.js
    output = {
        "vibe": vibe,
        "weeks": [b['label'] for b in buckets],
        "volume": {
            "swim": [b['data']['swim'] for b in buckets],
            "bike": [round(b['data']['bike'], 1) for b in buckets],
            "run": [round(b['data']['run'], 1) for b in buckets],
            "strength": [b['data']['strength_vol'] for b in buckets]
        },
        "compliance": {
            "score": [round(b['data']['compliance_sum'] / b['data']['compliance_count']) if b['data']['compliance_count'] > 0 else 0 for b in buckets]
        },
        "engagement": {
            "human": [b['data']['human_posts'] for b in buckets],
            "ai": [b['data']['ai_posts'] for b in buckets]
        }
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"✅ Data built for charts: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_json()
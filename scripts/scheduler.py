import os
import frontmatter # pip install python-frontmatter
from datetime import datetime

# CONFIGURATION
# ----------------------------------------------------------------
VAULT_DIR = "content/logs"       # Where the daily files go
PROTOCOL_DIR = "content/config"  # Where weekly plans live
TEMPLATE_DIR = "templates"       # Where the raw templates are

def get_todays_mission():
    """
    Finds the active Weekly Protocol and extracts today's specific orders.
    """
    today = datetime.now()
    year, week, _ = today.isocalendar()
    day_name = today.strftime("%A").lower() # e.g. "tuesday"
    
    # Look for file: content/config/protocol_2025-W49.md
    protocol_file = f"protocol_{year}-W{week:02d}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)
    
    mission = {"type": "Rest", "desc": "No protocol found."}

    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                data = frontmatter.load(f)
            
            # Navigate YAML: schedule -> tuesday
            schedule = data.get('schedule', {})
            daily_plan = schedule.get(day_name)
            
            if daily_plan:
                mission = daily_plan
        except Exception as e:
            print(f"⚠️ Error reading protocol: {e}")
            
    return mission

def create_daily_log():
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    
    # Page Bundle Structure: content/logs/2025-12-03/index.md
    folder_path = os.path.join(VAULT_DIR, date_str)
    file_path = os.path.join(folder_path, "index.md")

    # 1. Get Orders
    mission = get_todays_mission()

    # 2. Create Folder
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # 3. Create File
    if not os.path.exists(file_path):
        with open(os.path.join(TEMPLATE_DIR, "daily_log.md"), "r", encoding='utf-8') as t:
            content = t.read()
        
        # Inject Date
        content = content.replace("{{date:YYYY-MM-DD}}", date_str)
        content = content.replace("{{date:DDD}}", str(today.timetuple().tm_yday))
        
        # Inject Mission (The "Accountability" Hook)
        content = content.replace("{{plan_type}}", mission.get('type', 'Rest'))
        content = content.replace("{{plan_desc}}", mission.get('desc', 'Active Recovery'))
        
        with open(file_path, "w", encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Generated Log for {date_str} | Mission: {mission.get('type')}")
    else:
        print(f"⏭️  Log already exists for {date_str}")

if __name__ == "__main__":
    create_daily_log()
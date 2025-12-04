import os
import frontmatter
import yaml
import requests
import json
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3" 
LOGS_DIR = "content/logs"
PROFILE_PATH = "data/profile.yaml"

def query_ollama(messages):
    payload = { "model": MODEL, "messages": messages, "format": "json", "stream": False }
    try:
        r = requests.post(OLLAMA_URL, json=payload)
        return r.json()['message']['content']
    except:
        return None

def analyze_daily_fuel(log_path):
    post = frontmatter.load(log_path)
    if post['diet'].get('est_calories', 0) > 0: return # Skip if done
    
    if "## 🥗 Fuel Log" in post.content:
        fuel_text = post.content.split("## 🥗 Fuel Log")[1].split("---")[0].strip()
        if len(fuel_text) > 10:
            print(f"🤖 Analyzing Fuel: {log_path}")
            prompt = f"Analyze food log. Return JSON: {{calories, protein, carbs, fat}}. Log: {fuel_text}"
            
            resp = query_ollama([{"role": "user", "content": prompt}])
            if resp:
                data = json.loads(resp)
                post['diet'].update({
                    'est_calories': int(data.get('calories', 0)),
                    'est_protein_g': int(data.get('protein', 0)),
                    'est_carbs_g': int(data.get('carbs', 0)),
                    'est_fat_g': int(data.get('fat', 0))
                })
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write(frontmatter.dumps(post))

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOGS_DIR, today, "index.md")
    if os.path.exists(path): analyze_daily_fuel(path)
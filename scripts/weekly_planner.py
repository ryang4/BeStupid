"""
Weekly Protocol Planner - AI-Generated Training Plans

Generates next week's training protocol using Ollama (qwen).
Reads: ryan.md + last week's protocol + last week's logs
Outputs: protocol_YYYY-WXX_DRAFT.md for human review

Usage:
    python weekly_planner.py                    # Generate next week
    python weekly_planner.py --week 50          # Generate specific week
    python weekly_planner.py --finalize         # Remove _DRAFT suffix
"""

import os
import sys
import argparse
import frontmatter
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from llm_client import generate_weekly_protocol

# CONFIGURATION
RYAN_CONFIG = "content/config/ryan.md"
PROTOCOL_DIR = "content/config"
LOGS_DIR = "content/logs"


def get_next_week():
    """Calculate next week's year and week number."""
    today = datetime.now()
    next_week = today + timedelta(days=7)
    year, week, _ = next_week.isocalendar()
    return year, week


def read_last_protocol(year, week):
    """Read last week's protocol file."""
    last_week = week - 1
    last_year = year

    # Handle year transition
    if last_week < 1:
        last_year = year - 1
        # Get last week of previous year
        dec_31 = datetime(last_year, 12, 31)
        last_week = dec_31.isocalendar()[1]

    protocol_file = f"protocol_{last_year}-W{last_week:02d}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)

    if os.path.exists(protocol_path):
        with open(protocol_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def read_last_week_logs(year, week):
    """Read all daily logs from last week."""
    logs = []

    # Calculate last week's date range
    last_week = week - 1
    last_year = year
    if last_week < 1:
        last_year = year - 1
        dec_31 = datetime(last_year, 12, 31)
        last_week = dec_31.isocalendar()[1]

    # Get Monday of last week
    # ISO week 1 starts on the first Monday of the year
    jan_4 = datetime(last_year, 1, 4)  # Week 1 always contains Jan 4
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    target_monday = week_1_monday + timedelta(weeks=last_week - 1)

    # Read 7 days of logs
    for day_offset in range(7):
        log_date = target_monday + timedelta(days=day_offset)
        log_date_str = log_date.strftime("%Y-%m-%d")
        log_path = os.path.join(LOGS_DIR, log_date_str, "index.md")

        if os.path.exists(log_path):
            try:
                post = frontmatter.load(log_path)

                log_data = {
                    "date": log_date_str,
                    "content": post.content,
                    "stats": {
                        "compliance": post.get('Compliance', 0),
                        "sleep_hours": post.get('Sleep Hours', 0),
                        "weight": post.get('Weight (lbs)', 0),
                    },
                    "narrative": post.content  # Full text for AI analysis
                }
                logs.append(log_data)
            except Exception as e:
                print(f"⚠️  Warning: Could not read {log_path}: {e}")

    return logs


def main():
    parser = argparse.ArgumentParser(description="Generate weekly training protocol")
    parser.add_argument('--week', type=int, help='Specific week number to generate')
    parser.add_argument('--finalize', action='store_true', help='Remove _DRAFT suffix from latest protocol')
    args = parser.parse_args()

    # Handle finalize mode
    if args.finalize:
        # Find most recent DRAFT file
        draft_files = [f for f in os.listdir(PROTOCOL_DIR) if f.endswith('_DRAFT.md')]
        if not draft_files:
            print("❌ No DRAFT protocol files found")
            sys.exit(1)

        latest_draft = sorted(draft_files)[-1]
        draft_path = os.path.join(PROTOCOL_DIR, latest_draft)
        final_path = draft_path.replace('_DRAFT.md', '.md')

        os.rename(draft_path, final_path)
        print(f"✅ Finalized: {latest_draft} → {os.path.basename(final_path)}")
        sys.exit(0)

    # Determine target week
    if args.week:
        year = datetime.now().year
        week = args.week
    else:
        year, week = get_next_week()

    print(f"📅 Generating protocol for {year}-W{week:02d}...")

    # Read inputs
    print("📖 Reading Ryan's goals...")
    with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
        goals = f.read()

    print("📖 Reading last week's protocol...")
    last_protocol = read_last_protocol(year, week)
    if last_protocol:
        print("   ✓ Found previous protocol")
    else:
        print("   ℹ️  No previous protocol (first week)")

    print("📖 Reading last week's logs...")
    last_week_logs = read_last_week_logs(year, week)
    print(f"   ✓ Found {len(last_week_logs)} daily logs")

    # Generate protocol using AI
    print(f"🤖 Calling Ollama (qwen) to generate protocol...")
    print("   (This may take 30-60 seconds...)")

    try:
        protocol_content = generate_weekly_protocol(goals, last_protocol, last_week_logs)
    except ConnectionError as e:
        print(f"\n{e}")
        print("\n💡 To fix: Run 'ollama serve' in another terminal")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error generating protocol: {e}")
        sys.exit(1)

    # Save as DRAFT
    output_filename = f"protocol_{year}-W{week:02d}_DRAFT.md"
    output_path = os.path.join(PROTOCOL_DIR, output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(protocol_content)

    print(f"\n✅ Protocol generated: {output_filename}")
    print(f"\n📝 Next steps:")
    print(f"   1. Review/edit in Obsidian: {output_path}")
    print(f"   2. When ready, finalize: python weekly_planner.py --finalize")
    print(f"   3. Or manually rename to: protocol_{year}-W{week:02d}.md")


if __name__ == "__main__":
    main()

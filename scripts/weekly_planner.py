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
    """
    Calculate next week's Monday date.

    Returns:
        tuple: (year, week_number, monday_date_str)
    """
    today = datetime.now()
    # Find next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # If today is Monday, get next Monday
    next_monday = today + timedelta(days=days_until_monday)
    year, week, _ = next_monday.isocalendar()
    monday_str = next_monday.strftime("%Y-%m-%d")
    return year, week, monday_str


def read_last_protocol(target_monday_str):
    """
    Read last week's protocol file.

    Args:
        target_monday_str: Monday date of target week (YYYY-MM-DD)

    Returns:
        str or None: Protocol content if found
    """
    # Calculate last week's Monday
    target_monday = datetime.strptime(target_monday_str, "%Y-%m-%d")
    last_monday = target_monday - timedelta(days=7)
    last_monday_str = last_monday.strftime("%Y-%m-%d")

    # Try new date-based format first
    protocol_file = f"protocol_{last_monday_str}.md"
    protocol_path = os.path.join(PROTOCOL_DIR, protocol_file)

    if os.path.exists(protocol_path):
        with open(protocol_path, 'r', encoding='utf-8') as f:
            return f.read()

    # Fallback to old week-number format during transition
    year, week, _ = last_monday.isocalendar()
    old_protocol_file = f"protocol_{year}-W{week:02d}.md"
    old_protocol_path = os.path.join(PROTOCOL_DIR, old_protocol_file)

    if os.path.exists(old_protocol_path):
        print(f"Note: Using legacy protocol format {old_protocol_file}")
        with open(old_protocol_path, 'r', encoding='utf-8') as f:
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
        # Flat file path (not page bundle)
        log_path = os.path.join(LOGS_DIR, f"{log_date_str}.md")

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
    parser.add_argument('--date', type=str, help='Specific Monday date (YYYY-MM-DD) to generate')
    parser.add_argument('--finalize', action='store_true', help='Remove _DRAFT suffix from latest protocol')
    args = parser.parse_args()

    # Handle finalize mode
    if args.finalize:
        # Find most recent DRAFT file
        draft_files = [f for f in os.listdir(PROTOCOL_DIR) if f.endswith('_DRAFT.md')]
        if not draft_files:
            print("No DRAFT protocol files found")
            sys.exit(1)

        latest_draft = sorted(draft_files)[-1]
        draft_path = os.path.join(PROTOCOL_DIR, latest_draft)
        final_path = draft_path.replace('_DRAFT.md', '.md')

        os.rename(draft_path, final_path)
        print(f"Finalized: {latest_draft} -> {os.path.basename(final_path)}")
        sys.exit(0)

    # Determine target week
    if args.date:
        monday_str = args.date
        target_monday = datetime.strptime(monday_str, "%Y-%m-%d")
        year, week, _ = target_monday.isocalendar()
    elif args.week:
        year = datetime.now().year
        week = args.week
        # Calculate Monday for that week
        jan_4 = datetime(year, 1, 4)
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        target_monday = week_1_monday + timedelta(weeks=week - 1)
        monday_str = target_monday.strftime("%Y-%m-%d")
    else:
        year, week, monday_str = get_next_week()

    print(f"Generating protocol for week of {monday_str} (W{week:02d})...")

    # Read inputs
    print("Reading Ryan's goals...")
    with open(RYAN_CONFIG, 'r', encoding='utf-8') as f:
        goals = f.read()

    print("Reading last week's protocol...")
    last_protocol = read_last_protocol(monday_str)
    if last_protocol:
        print("   Found previous protocol")
    else:
        print("   No previous protocol (first week)")

    print("Reading last week's logs...")
    last_week_logs = read_last_week_logs(year, week)
    print(f"   Found {len(last_week_logs)} daily logs")

    # Generate protocol using AI
    print("Generating weekly protocol...")
    print("   (This may take 30-60 seconds...)")

    try:
        protocol_content = generate_weekly_protocol(goals, last_protocol, last_week_logs)
    except RuntimeError as e:
        # This catches when all LLM backends fail
        print(f"\n{e}")
        print("\nTo fix: Set HF_TOKEN in .env file or run 'ollama serve' in another terminal")
        sys.exit(1)
    except Exception as e:
        print(f"\nError generating protocol: {e}")
        sys.exit(1)

    # Save as DRAFT with date-based naming
    output_filename = f"protocol_{monday_str}_DRAFT.md"
    output_path = os.path.join(PROTOCOL_DIR, output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(protocol_content)

    print(f"\nProtocol generated: {output_filename}")
    print("\nNext steps:")
    print(f"   1. Review/edit in Obsidian: {output_path}")
    print("   2. When ready, finalize: python weekly_planner.py --finalize")
    print(f"   3. Or manually rename to: protocol_{monday_str}.md")


if __name__ == "__main__":
    main()

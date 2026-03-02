#!/usr/bin/env python3
"""
Migrate existing memory data into brain.db.

Idempotent — safe to re-run. Does NOT delete original JSON files.

Migrates:
- decisions/*.json → entities + documents
- commitments/*.json → entities + documents
- people/*.json → entities + documents
- events.jsonl → events table
- content/logs/*.md → documents (each section as a separate doc)
"""

import json
import logging
import sys
from pathlib import Path

# Add scripts dir to path for brain_db import
sys.path.insert(0, str(Path(__file__).parent))

from brain_db import (
    get_connection,
    init_schema,
    store_document,
    store_entity,
    store_event,
    embed_and_store_document,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_ROOT = PROJECT_ROOT / "memory"
LOGS_DIR = PROJECT_ROOT / "content" / "logs"


def migrate_decisions(conn):
    """Migrate decisions/*.json into entities and documents."""
    decisions_dir = MEMORY_ROOT / "decisions"
    if not decisions_dir.exists():
        return 0

    count = 0
    for filepath in decisions_dir.glob("*.json"):
        try:
            data = json.loads(filepath.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Skipping corrupt file: {filepath}")
            continue

        name = data.get("topic", filepath.stem)
        props = {
            "choice": data.get("choice", ""),
            "rationale": data.get("rationale", ""),
            "context": data.get("context", ""),
            "status": data.get("status", "active"),
            "reversible": data.get("reversible", True),
        }

        store_entity(name, "decision", props, conn=conn)

        content = f"Decision: {name}\nChoice: {props['choice']}\nRationale: {props['rationale']}\nContext: {props['context']}"
        store_document(
            doc_type="entity",
            content=content,
            title=f"Decision: {name}",
            source=f"memory/decisions/{filepath.name}",
            metadata={"migrated_from": str(filepath), "original_created": data.get("created", "")},
            conn=conn,
        )
        count += 1

    logger.info(f"Migrated {count} decisions")
    return count


def migrate_commitments(conn):
    """Migrate commitments/*.json into entities and documents."""
    commitments_dir = MEMORY_ROOT / "commitments"
    if not commitments_dir.exists():
        return 0

    count = 0
    for filepath in sorted(commitments_dir.glob("*.json")):
        try:
            data = json.loads(filepath.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Skipping corrupt file: {filepath}")
            continue

        name = data.get("what", filepath.stem)
        props = {
            "deadline": data.get("deadline", ""),
            "who": data.get("who", ""),
            "context": data.get("context", ""),
            "priority": data.get("priority", "normal"),
            "status": data.get("status", "open"),
        }

        store_entity(name, "commitment", props, conn=conn)

        content = f"Commitment: {name}\nDeadline: {props['deadline']}\nWho: {props['who']}\nContext: {props['context']}\nStatus: {props['status']}"
        store_document(
            doc_type="entity",
            content=content,
            title=f"Commitment: {name}",
            source=f"memory/commitments/{filepath.name}",
            metadata={"migrated_from": str(filepath), "original_created": data.get("created", "")},
            conn=conn,
        )
        count += 1

    logger.info(f"Migrated {count} commitments")
    return count


def migrate_people(conn):
    """Migrate people/*.json into entities and documents."""
    people_dir = MEMORY_ROOT / "people"
    if not people_dir.exists():
        return 0

    count = 0
    for filepath in people_dir.glob("*.json"):
        try:
            data = json.loads(filepath.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Skipping corrupt file: {filepath}")
            continue

        name = data.get("name", filepath.stem)
        props = {
            "role": data.get("role", ""),
            "context": data.get("context", ""),
            "source": data.get("source", ""),
            "tags": data.get("tags", []),
            "notes": data.get("notes", ""),
        }

        store_entity(name, "person", props, conn=conn)

        content = f"Person: {name}\nRole: {props['role']}\nContext: {props['context']}\nNotes: {props['notes']}"
        store_document(
            doc_type="entity",
            content=content,
            title=f"Person: {name}",
            source=f"memory/people/{filepath.name}",
            metadata={"migrated_from": str(filepath)},
            conn=conn,
        )
        count += 1

    logger.info(f"Migrated {count} people")
    return count


def migrate_events(conn):
    """Migrate events.jsonl into events table."""
    events_path = MEMORY_ROOT / "events.jsonl"
    if not events_path.exists():
        return 0

    count = 0
    with open(events_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            store_event(
                event_type=event.get("type", "unknown"),
                agent=event.get("agent", ""),
                action=event.get("action", ""),
                entity=event.get("entity", ""),
                metadata=event.get("meta", {}),
                conn=conn,
            )
            count += 1

    logger.info(f"Migrated {count} events")
    return count


def migrate_daily_logs(conn, embed: bool = False):
    """Migrate content/logs/*.md into documents.

    Each log file becomes a document. Embedding is optional (costs API calls).
    """
    if not LOGS_DIR.exists():
        return 0

    count = 0
    for log_file in sorted(LOGS_DIR.glob("*.md")):
        date_str = log_file.stem
        # Skip non-date files
        if not (len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-"):
            continue

        try:
            content = log_file.read_text()
        except OSError:
            continue

        doc_id = store_document(
            doc_type="log_entry",
            content=content,
            title=f"Daily Log {date_str}",
            source=f"content/logs/{log_file.name}",
            metadata={"date": date_str},
            conn=conn,
        )

        if embed:
            embed_and_store_document(doc_id, content, conn=conn)

        count += 1

    logger.info(f"Migrated {count} daily logs" + (" (with embeddings)" if embed else ""))
    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate existing data to brain.db")
    parser.add_argument("--embed", action="store_true", help="Generate embeddings during migration (costs API calls)")
    args = parser.parse_args()

    conn = get_connection()
    init_schema(conn)

    # Check if already migrated
    row = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()
    if row["c"] > 0:
        logger.info(f"Brain DB already has {row['c']} documents. Running additive migration (duplicates possible).")

    total = 0
    total += migrate_decisions(conn)
    total += migrate_commitments(conn)
    total += migrate_people(conn)
    total += migrate_events(conn)
    total += migrate_daily_logs(conn, embed=args.embed)

    conn.close()

    logger.info(f"Migration complete. {total} items migrated to {MEMORY_ROOT / 'brain.db'}")
    logger.info("Original JSON files preserved as backup.")


if __name__ == "__main__":
    main()

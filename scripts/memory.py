#!/usr/bin/env python3
"""
Memory management tools for the BeStupid knowledge graph.
Provides deterministic CRUD operations for structured memory storage.

Usage:
    python memory.py people add "John Smith" --context "Met at tech conference" --source "Notion" --role "PM candidate"
    python memory.py people get "John Smith"
    python memory.py people update "John Smith" --field role --value "Hired as PM"
    python memory.py people list
    python memory.py people delete "John Smith"

    python memory.py projects add "startup" --status "active" --description "Building the MVP"
    python memory.py decisions add "tech-stack" --choice "React + FastAPI" --rationale "Team expertise"
    python memory.py commitments add "Send proposal to John" --deadline "2026-01-30" --context "Discussed at coffee"
"""

import argparse
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import ulid

MEMORY_ROOT = Path(__file__).parent.parent / "memory"
EVENTS_PATH = MEMORY_ROOT / "events.jsonl"

# Ensure directories exist
for category in ["people", "projects", "decisions", "commitments"]:
    (MEMORY_ROOT / category).mkdir(parents=True, exist_ok=True)


# =============================================================================
# EVENT LOG
# =============================================================================

def append_event(type: str, agent: str, action: str, entity: str = "", meta: dict = None):
    """Atomically append event to JSONL log."""
    entry = {
        "v": 1,
        "id": str(ulid.ULID()),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "type": type,
        "agent": agent,
        "action": action,
        "entity": entity,
        "meta": meta or {},
    }
    line = json.dumps(entry, separators=(",", ":")) + "\n"
    with open(EVENTS_PATH, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def query_events(type=None, agent=None, since=None, limit=100):
    """Stream-parse JSONL with filters, skipping corrupt lines."""
    results = []
    if not EVENTS_PATH.exists():
        return results
    with open(EVENTS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type and event.get("type") != type:
                continue
            if agent and event.get("agent") != agent:
                continue
            if since and event.get("ts", "") < since:
                continue
            results.append(event)
    return results[-limit:]


def slugify(name: str) -> str:
    """Convert name to filesystem-safe slug."""
    return name.lower().replace(" ", "-").replace(".", "").replace(",", "")


def get_timestamp() -> str:
    """Get current ISO timestamp."""
    return datetime.now().isoformat()


# =============================================================================
# PEOPLE
# =============================================================================

def people_add(name: str, context: str = "", source: str = "", role: str = "",
               tags: list = None, notes: str = "") -> dict:
    """Add a new person to memory."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "people" / f"{slug}.json"

    if filepath.exists():
        print(f"Person '{name}' already exists. Use 'update' to modify.", file=sys.stderr)
        return people_get(name)

    person = {
        "name": name,
        "slug": slug,
        "context": context,
        "source": source,
        "role": role,
        "tags": tags or [],
        "notes": notes,
        "interactions": [],
        "created": get_timestamp(),
        "updated": get_timestamp()
    }

    filepath.write_text(json.dumps(person, indent=2))
    append_event("memory_write", "cli", "people.add", f"people/{slug}")
    print(f"Added person: {name}")
    return person


def people_get(name: str) -> Optional[dict]:
    """Get a person by name."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "people" / f"{slug}.json"

    if not filepath.exists():
        print(f"Person '{name}' not found.", file=sys.stderr)
        return None

    person = json.loads(filepath.read_text())
    print(json.dumps(person, indent=2))
    return person


def people_update(name: str, field: str, value: str) -> Optional[dict]:
    """Update a field for a person."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "people" / f"{slug}.json"

    if not filepath.exists():
        print(f"Person '{name}' not found.", file=sys.stderr)
        return None

    person = json.loads(filepath.read_text())

    # Handle list fields
    if field == "tags":
        if value not in person["tags"]:
            person["tags"].append(value)
    elif field == "interaction":
        person["interactions"].append({
            "date": get_timestamp(),
            "note": value
        })
    else:
        person[field] = value

    person["updated"] = get_timestamp()
    filepath.write_text(json.dumps(person, indent=2))
    append_event("memory_write", "cli", "people.update", f"people/{slug}", {"field": field})
    print(f"Updated {name}.{field}")
    return person


def people_list() -> list:
    """List all people in memory."""
    people = []
    for filepath in (MEMORY_ROOT / "people").glob("*.json"):
        person = json.loads(filepath.read_text())
        people.append({
            "name": person["name"],
            "role": person.get("role", ""),
            "source": person.get("source", ""),
            "updated": person.get("updated", "")
        })

    print(json.dumps(people, indent=2))
    return people


def people_delete(name: str) -> bool:
    """Delete a person from memory."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "people" / f"{slug}.json"

    if not filepath.exists():
        print(f"Person '{name}' not found.", file=sys.stderr)
        return False

    filepath.unlink()
    append_event("memory_write", "cli", "people.delete", f"people/{slug}")
    print(f"Deleted person: {name}")
    return True


# =============================================================================
# PROJECTS
# =============================================================================

def projects_add(name: str, status: str = "active", description: str = "",
                 goals: list = None, blockers: list = None) -> dict:
    """Add a new project to memory."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "projects" / f"{slug}.json"

    if filepath.exists():
        print(f"Project '{name}' already exists. Use 'update' to modify.", file=sys.stderr)
        return projects_get(name)

    project = {
        "name": name,
        "slug": slug,
        "status": status,
        "description": description,
        "goals": goals or [],
        "blockers": blockers or [],
        "updates": [],
        "created": get_timestamp(),
        "updated": get_timestamp()
    }

    filepath.write_text(json.dumps(project, indent=2))
    append_event("memory_write", "cli", "projects.add", f"projects/{slug}")
    print(f"Added project: {name}")
    return project


def projects_get(name: str) -> Optional[dict]:
    """Get a project by name."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "projects" / f"{slug}.json"

    if not filepath.exists():
        print(f"Project '{name}' not found.", file=sys.stderr)
        return None

    project = json.loads(filepath.read_text())
    print(json.dumps(project, indent=2))
    return project


def projects_update(name: str, field: str, value: str) -> Optional[dict]:
    """Update a field for a project."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "projects" / f"{slug}.json"

    if not filepath.exists():
        print(f"Project '{name}' not found.", file=sys.stderr)
        return None

    project = json.loads(filepath.read_text())

    if field == "goal":
        project["goals"].append(value)
    elif field == "blocker":
        project["blockers"].append(value)
    elif field == "update":
        project["updates"].append({
            "date": get_timestamp(),
            "note": value
        })
    elif field == "resolve_blocker":
        project["blockers"] = [b for b in project["blockers"] if b != value]
    else:
        project[field] = value

    project["updated"] = get_timestamp()
    filepath.write_text(json.dumps(project, indent=2))
    append_event("memory_write", "cli", "projects.update", f"projects/{slug}", {"field": field})
    print(f"Updated {name}.{field}")
    return project


def projects_list() -> list:
    """List all projects in memory."""
    projects = []
    for filepath in (MEMORY_ROOT / "projects").glob("*.json"):
        project = json.loads(filepath.read_text())
        projects.append({
            "name": project["name"],
            "status": project.get("status", ""),
            "updated": project.get("updated", "")
        })

    print(json.dumps(projects, indent=2))
    return projects


def projects_delete(name: str) -> bool:
    """Delete a project from memory."""
    slug = slugify(name)
    filepath = MEMORY_ROOT / "projects" / f"{slug}.json"

    if not filepath.exists():
        print(f"Project '{name}' not found.", file=sys.stderr)
        return False

    filepath.unlink()
    append_event("memory_write", "cli", "projects.delete", f"projects/{slug}")
    print(f"Deleted project: {name}")
    return True


# =============================================================================
# DECISIONS
# =============================================================================

def decisions_add(topic: str, choice: str, rationale: str = "",
                  context: str = "", reversible: bool = True) -> dict:
    """Add a new decision to memory."""
    slug = slugify(topic)
    filepath = MEMORY_ROOT / "decisions" / f"{slug}.json"

    decision = {
        "topic": topic,
        "slug": slug,
        "choice": choice,
        "rationale": rationale,
        "context": context,
        "reversible": reversible,
        "status": "active",
        "created": get_timestamp(),
        "updated": get_timestamp()
    }

    # If decision exists, archive old and create new
    if filepath.exists():
        old = json.loads(filepath.read_text())
        old["status"] = "superseded"
        old["superseded_by"] = decision["created"]
        archive_path = MEMORY_ROOT / "decisions" / f"{slug}-{old['created'][:10]}.json"
        archive_path.write_text(json.dumps(old, indent=2))

    filepath.write_text(json.dumps(decision, indent=2))
    append_event("memory_write", "cli", "decisions.add", f"decisions/{slug}")
    print(f"Added decision: {topic} -> {choice}")
    return decision


def decisions_get(topic: str) -> Optional[dict]:
    """Get a decision by topic."""
    slug = slugify(topic)
    filepath = MEMORY_ROOT / "decisions" / f"{slug}.json"

    if not filepath.exists():
        print(f"Decision '{topic}' not found.", file=sys.stderr)
        return None

    decision = json.loads(filepath.read_text())
    print(json.dumps(decision, indent=2))
    return decision


def decisions_list() -> list:
    """List all active decisions."""
    decisions = []
    for filepath in (MEMORY_ROOT / "decisions").glob("*.json"):
        decision = json.loads(filepath.read_text())
        if decision.get("status") == "active":
            decisions.append({
                "topic": decision["topic"],
                "choice": decision["choice"],
                "created": decision.get("created", "")
            })

    print(json.dumps(decisions, indent=2))
    return decisions


def decisions_revoke(topic: str, reason: str = "") -> Optional[dict]:
    """Revoke a decision."""
    slug = slugify(topic)
    filepath = MEMORY_ROOT / "decisions" / f"{slug}.json"

    if not filepath.exists():
        print(f"Decision '{topic}' not found.", file=sys.stderr)
        return None

    decision = json.loads(filepath.read_text())
    decision["status"] = "revoked"
    decision["revoked_reason"] = reason
    decision["updated"] = get_timestamp()

    filepath.write_text(json.dumps(decision, indent=2))
    append_event("memory_write", "cli", "decisions.revoke", f"decisions/{slug}")
    print(f"Revoked decision: {topic}")
    return decision


# =============================================================================
# COMMITMENTS
# =============================================================================

def commitments_add(what: str, deadline: str = "", who: str = "",
                    context: str = "", priority: str = "normal") -> dict:
    """Add a new commitment to memory."""
    slug = slugify(what)[:50]  # Truncate long commitments
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filepath = MEMORY_ROOT / "commitments" / f"{timestamp}-{slug}.json"

    commitment = {
        "what": what,
        "who": who,
        "deadline": deadline,
        "context": context,
        "priority": priority,
        "status": "open",
        "created": get_timestamp(),
        "updated": get_timestamp()
    }

    filepath.write_text(json.dumps(commitment, indent=2))
    append_event("memory_write", "cli", "commitments.add", f"commitments/{filepath.stem}")
    print(f"Added commitment: {what}")
    return commitment


def commitments_list(status: str = "open") -> list:
    """List commitments by status."""
    commitments = []
    for filepath in sorted((MEMORY_ROOT / "commitments").glob("*.json")):
        commitment = json.loads(filepath.read_text())
        if status == "all" or commitment.get("status") == status:
            commitments.append({
                "what": commitment["what"],
                "who": commitment.get("who", ""),
                "deadline": commitment.get("deadline", ""),
                "status": commitment.get("status", "open"),
                "file": filepath.name
            })

    print(json.dumps(commitments, indent=2))
    return commitments


def commitments_complete(what: str) -> bool:
    """Mark a commitment as complete."""
    for filepath in (MEMORY_ROOT / "commitments").glob("*.json"):
        commitment = json.loads(filepath.read_text())
        if commitment["what"].lower() == what.lower():
            commitment["status"] = "complete"
            commitment["completed"] = get_timestamp()
            commitment["updated"] = get_timestamp()
            filepath.write_text(json.dumps(commitment, indent=2))
            append_event("memory_write", "cli", "commitments.complete", f"commitments/{filepath.stem}")
            print(f"Completed: {what}")
            return True

    print(f"Commitment '{what}' not found.", file=sys.stderr)
    return False


def commitments_cancel(what: str, reason: str = "") -> bool:
    """Cancel a commitment."""
    for filepath in (MEMORY_ROOT / "commitments").glob("*.json"):
        commitment = json.loads(filepath.read_text())
        if commitment["what"].lower() == what.lower():
            commitment["status"] = "cancelled"
            commitment["cancel_reason"] = reason
            commitment["updated"] = get_timestamp()
            filepath.write_text(json.dumps(commitment, indent=2))
            append_event("memory_write", "cli", "commitments.cancel", f"commitments/{filepath.stem}")
            print(f"Cancelled: {what}")
            return True

    print(f"Commitment '{what}' not found.", file=sys.stderr)
    return False


# =============================================================================
# SEARCH (across all categories)
# =============================================================================

def search(query: str) -> list:
    """Search across all memory categories."""
    query_lower = query.lower()
    results = []

    for category in ["people", "projects", "decisions", "commitments"]:
        for filepath in (MEMORY_ROOT / category).glob("*.json"):
            content = filepath.read_text()
            if query_lower in content.lower():
                data = json.loads(content)
                results.append({
                    "category": category,
                    "file": filepath.name,
                    "data": data
                })

    print(json.dumps(results, indent=2))
    return results


# =============================================================================
# AUTO-EXTRACTION
# =============================================================================

ALLOWED_OPS = {
    "people.add": people_add,
    "people.update": people_update,
    "projects.add": projects_add,
    "projects.update": projects_update,
    "decisions.add": decisions_add,
    "commitments.add": commitments_add,
    "commitments.complete": commitments_complete,
}

EXTRACTION_PROMPT = """You are a Personal Information Organizer. Extract concrete facts from this interaction.
Return a JSON array of operations:
[
  {{"op": "people.add", "args": {{"name": "...", "context": "...", "role": "..."}}}},
  {{"op": "projects.update", "args": {{"name": "...", "field": "update", "value": "..."}}}},
  {{"op": "commitments.add", "args": {{"what": "...", "deadline": "...", "context": "..."}}}}
]
Return [] if nothing worth persisting. Only extract CONCRETE facts — preferences, decisions,
relationships, project context. Ignore transient conversation ("thanks", "ok").

Interaction:
{interaction_text}"""


def extract_and_persist(interaction_text: str, agent: str = "extractor"):
    """Extract facts from interaction, dispatch to CRUD, log events.

    Tries Claude Code CLI first (Claude Max, $0/token), falls back to Anthropic API.
    """
    import os

    prompt = EXTRACTION_PROMPT.format(interaction_text=interaction_text[:4000])
    operations = None

    # Try CLI first (uses Claude Max subscription, $0/token)
    try:
        from claude_cli import call_claude_json, cli_available
        if cli_available():
            result = call_claude_json(
                prompt,
                system_prompt="Return only a valid JSON array. No explanation or markdown.",
            )
            if isinstance(result, list):
                operations = result
    except ImportError:
        pass

    # Fall back to Anthropic API
    if operations is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            append_event("extraction_failed", agent, "no_api_key_or_cli")
            return []

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response = message.content[0].text
        except Exception as e:
            append_event("extraction_failed", agent, f"api_error: {e}")
            return []

        # Robust JSON extraction: handle markdown code blocks
        raw = response
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        try:
            operations = json.loads(raw.strip())
        except json.JSONDecodeError:
            append_event("extraction_failed", agent, "json_parse_error")
            return []

    if not isinstance(operations, list):
        return []

    results = []
    cid = str(ulid.ULID())
    for op in operations:
        op_name = op.get("op", "")
        if op_name not in ALLOWED_OPS:
            continue
        args = op.get("args", {})
        if not isinstance(args, dict):
            continue
        # Validate: all values must be strings, lists, or bools; no path separators
        if not all(isinstance(v, (str, list, bool)) for v in args.values()):
            continue
        if any("/" in str(v) or "\\" in str(v) for v in args.values() if isinstance(v, str)):
            continue
        try:
            ALLOWED_OPS[op_name](**args)
            results.append(op_name)
        except (TypeError, KeyError):
            continue

    append_event("extraction_complete", agent, f"extracted {len(results)} ops",
                 meta={"cid": cid, "ops": results})
    return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Memory management for BeStupid")
    subparsers = parser.add_subparsers(dest="category", help="Memory category")

    # People
    people_parser = subparsers.add_parser("people", help="Manage people/relationships")
    people_sub = people_parser.add_subparsers(dest="action")

    p_add = people_sub.add_parser("add", help="Add a person")
    p_add.add_argument("name", help="Person's name")
    p_add.add_argument("--context", default="", help="How you know them")
    p_add.add_argument("--source", default="", help="Where you met/found them")
    p_add.add_argument("--role", default="", help="Their role or your relationship")
    p_add.add_argument("--tags", nargs="*", default=[], help="Tags")
    p_add.add_argument("--notes", default="", help="Additional notes")

    p_get = people_sub.add_parser("get", help="Get a person")
    p_get.add_argument("name", help="Person's name")

    p_update = people_sub.add_parser("update", help="Update a person")
    p_update.add_argument("name", help="Person's name")
    p_update.add_argument("--field", required=True, help="Field to update")
    p_update.add_argument("--value", required=True, help="New value")

    p_list = people_sub.add_parser("list", help="List all people")

    p_delete = people_sub.add_parser("delete", help="Delete a person")
    p_delete.add_argument("name", help="Person's name")

    # Projects
    projects_parser = subparsers.add_parser("projects", help="Manage projects")
    projects_sub = projects_parser.add_subparsers(dest="action")

    pr_add = projects_sub.add_parser("add", help="Add a project")
    pr_add.add_argument("name", help="Project name")
    pr_add.add_argument("--status", default="active", help="Status")
    pr_add.add_argument("--description", default="", help="Description")

    pr_get = projects_sub.add_parser("get", help="Get a project")
    pr_get.add_argument("name", help="Project name")

    pr_update = projects_sub.add_parser("update", help="Update a project")
    pr_update.add_argument("name", help="Project name")
    pr_update.add_argument("--field", required=True, help="Field to update")
    pr_update.add_argument("--value", required=True, help="New value")

    pr_list = projects_sub.add_parser("list", help="List all projects")

    pr_delete = projects_sub.add_parser("delete", help="Delete a project")
    pr_delete.add_argument("name", help="Project name")

    # Decisions
    decisions_parser = subparsers.add_parser("decisions", help="Manage decisions")
    decisions_sub = decisions_parser.add_subparsers(dest="action")

    d_add = decisions_sub.add_parser("add", help="Add a decision")
    d_add.add_argument("topic", help="Decision topic")
    d_add.add_argument("--choice", required=True, help="What was decided")
    d_add.add_argument("--rationale", default="", help="Why")
    d_add.add_argument("--context", default="", help="Context")

    d_get = decisions_sub.add_parser("get", help="Get a decision")
    d_get.add_argument("topic", help="Decision topic")

    d_list = decisions_sub.add_parser("list", help="List active decisions")

    d_revoke = decisions_sub.add_parser("revoke", help="Revoke a decision")
    d_revoke.add_argument("topic", help="Decision topic")
    d_revoke.add_argument("--reason", default="", help="Why revoked")

    # Commitments
    commitments_parser = subparsers.add_parser("commitments", help="Manage commitments")
    commitments_sub = commitments_parser.add_subparsers(dest="action")

    c_add = commitments_sub.add_parser("add", help="Add a commitment")
    c_add.add_argument("what", help="What you committed to")
    c_add.add_argument("--deadline", default="", help="Deadline")
    c_add.add_argument("--who", default="", help="Who it's for")
    c_add.add_argument("--context", default="", help="Context")
    c_add.add_argument("--priority", default="normal", help="Priority")

    c_list = commitments_sub.add_parser("list", help="List commitments")
    c_list.add_argument("--status", default="open", help="Filter by status")

    c_complete = commitments_sub.add_parser("complete", help="Complete a commitment")
    c_complete.add_argument("what", help="What was committed")

    c_cancel = commitments_sub.add_parser("cancel", help="Cancel a commitment")
    c_cancel.add_argument("what", help="What was committed")
    c_cancel.add_argument("--reason", default="", help="Why cancelled")

    # Search
    search_parser = subparsers.add_parser("search", help="Search all memory")
    search_parser.add_argument("query", help="Search query")

    # History
    history_parser = subparsers.add_parser("history", help="Show recent events")
    history_parser.add_argument("--limit", type=int, default=20, help="Max events")
    history_parser.add_argument("--type", default=None, help="Filter by event type")
    history_parser.add_argument("--agent", default=None, help="Filter by agent")

    # Extract
    extract_parser = subparsers.add_parser("extract", help="Extract facts from text")
    extract_parser.add_argument("text", help="Interaction text to extract from")

    args = parser.parse_args()

    if args.category == "people":
        if args.action == "add":
            people_add(args.name, args.context, args.source, args.role, args.tags, args.notes)
        elif args.action == "get":
            people_get(args.name)
        elif args.action == "update":
            people_update(args.name, args.field, args.value)
        elif args.action == "list":
            people_list()
        elif args.action == "delete":
            people_delete(args.name)

    elif args.category == "projects":
        if args.action == "add":
            projects_add(args.name, args.status, args.description)
        elif args.action == "get":
            projects_get(args.name)
        elif args.action == "update":
            projects_update(args.name, args.field, args.value)
        elif args.action == "list":
            projects_list()
        elif args.action == "delete":
            projects_delete(args.name)

    elif args.category == "decisions":
        if args.action == "add":
            decisions_add(args.topic, args.choice, args.rationale, args.context)
        elif args.action == "get":
            decisions_get(args.topic)
        elif args.action == "list":
            decisions_list()
        elif args.action == "revoke":
            decisions_revoke(args.topic, args.reason)

    elif args.category == "commitments":
        if args.action == "add":
            commitments_add(args.what, args.deadline, args.who, args.context, args.priority)
        elif args.action == "list":
            commitments_list(args.status)
        elif args.action == "complete":
            commitments_complete(args.what)
        elif args.action == "cancel":
            commitments_cancel(args.what, args.reason)

    elif args.category == "search":
        search(args.query)

    elif args.category == "history":
        events = query_events(type=args.type, agent=args.agent, limit=args.limit)
        print(json.dumps(events, indent=2))

    elif args.category == "extract":
        results = extract_and_persist(args.text)
        print(f"Extracted {len(results)} operations: {results}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Brain DB — SQLite-backed second brain for BeStupid.

Stores documents, entities, relationships, embeddings, patterns, and preferences.
Uses OpenAI text-embedding-3-small for semantic search ($0.02/1M tokens).
"""

import json
import logging
import os
import re
import sqlite3
import struct
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Optional

import ulid

logger = logging.getLogger(__name__)

MEMORY_ROOT = Path(__file__).parent.parent / "memory"
DB_PATH = MEMORY_ROOT / "brain.db"

# Embedding config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_CHUNK_CHARS = 2000


# =============================================================================
# CONNECTION MANAGEMENT
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """Get a connection to brain.db with WAL mode for concurrent reads."""
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: Optional[sqlite3.Connection] = None):
    """Create all tables if they don't exist. Idempotent."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            doc_type TEXT NOT NULL,  -- conversation, log_entry, article, note, entity
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',  -- file path, chat_id, url
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'  -- JSON blob
        );

        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,  -- person, project, decision, commitment, fact, preference, pattern
            properties TEXT NOT NULL DEFAULT '{}',  -- JSON blob
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relationships (
            id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,  -- mentions, relates_to, decided, committed_to, etc.
            properties TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_entity_id) REFERENCES entities(id),
            FOREIGN KEY (target_entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL,  -- packed float32 array
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,  -- behavioral, food, productivity, mood, sleep
            description TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '[]',  -- JSON array of document IDs
            confidence REAL NOT NULL DEFAULT 0.0,
            detected_at TEXT NOT NULL,
            expires_at TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active'  -- active, expired, dismissed
        );

        CREATE TABLE IF NOT EXISTS preferences (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,  -- food, schedule, fitness, communication, work
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'inferred',  -- explicit, inferred
            confidence REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            agent TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL DEFAULT '',
            entity TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);
        CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_embeddings_document ON embeddings(document_id);
        CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);
        CREATE INDEX IF NOT EXISTS idx_preferences_category ON preferences(category);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
    """)
    conn.commit()

    if close_after:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _new_id() -> str:
    return str(ulid.ULID())


# =============================================================================
# DOCUMENTS CRUD
# =============================================================================

def store_document(
    doc_type: str,
    content: str,
    title: str = "",
    source: str = "",
    metadata: Optional[dict] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store a document and return its ID."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    doc_id = _new_id()
    now = _now()

    conn.execute(
        "INSERT INTO documents (id, doc_type, title, content, source, created_at, updated_at, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, doc_type, title, content, source, now, now, json.dumps(metadata or {})),
    )
    conn.commit()

    if close_after:
        conn.close()
    return doc_id


def get_document(doc_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    """Get a document by ID."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    if close_after:
        conn.close()
    return dict(row) if row else None


def search_documents_keyword(
    query: str,
    doc_type: Optional[str] = None,
    limit: int = 20,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Keyword search across document content and titles."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    query_lower = f"%{query.lower()}%"
    if doc_type:
        rows = conn.execute(
            "SELECT * FROM documents WHERE doc_type = ? AND (LOWER(content) LIKE ? OR LOWER(title) LIKE ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (doc_type, query_lower, query_lower, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM documents WHERE LOWER(content) LIKE ? OR LOWER(title) LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (query_lower, query_lower, limit),
        ).fetchall()

    if close_after:
        conn.close()
    return [dict(r) for r in rows]


def get_recent_documents(
    doc_type: Optional[str] = None,
    limit: int = 10,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Get most recent documents."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    if doc_type:
        rows = conn.execute(
            "SELECT * FROM documents WHERE doc_type = ? ORDER BY created_at DESC LIMIT ?",
            (doc_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if close_after:
        conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# ENTITIES CRUD
# =============================================================================

def store_entity(
    name: str,
    entity_type: str,
    properties: Optional[dict] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store or update an entity. Returns the entity ID."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    now = _now()

    # Check if entity already exists (by name + type)
    existing = conn.execute(
        "SELECT id, properties FROM entities WHERE LOWER(name) = LOWER(?) AND entity_type = ?",
        (name, entity_type),
    ).fetchone()

    if existing:
        # Merge properties
        old_props = json.loads(existing["properties"])
        old_props.update(properties or {})
        conn.execute(
            "UPDATE entities SET properties = ?, updated_at = ? WHERE id = ?",
            (json.dumps(old_props), now, existing["id"]),
        )
        conn.commit()
        entity_id = existing["id"]
    else:
        entity_id = _new_id()
        conn.execute(
            "INSERT INTO entities (id, name, entity_type, properties, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity_id, name, entity_type, json.dumps(properties or {}), now, now),
        )
        conn.commit()

    if close_after:
        conn.close()
    return entity_id


def get_entity(entity_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    """Get an entity by ID."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()

    if close_after:
        conn.close()
    return dict(row) if row else None


def find_entities(
    name: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 20,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Find entities by name and/or type."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    conditions = []
    params = []
    if name:
        conditions.append("LOWER(name) LIKE ?")
        params.append(f"%{name.lower()}%")
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM entities WHERE {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()

    if close_after:
        conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# RELATIONSHIPS
# =============================================================================

def store_relationship(
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    properties: Optional[dict] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store a relationship between entities. Returns the relationship ID."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    # Check for existing relationship
    existing = conn.execute(
        "SELECT id FROM relationships WHERE source_entity_id = ? AND target_entity_id = ? AND relationship_type = ?",
        (source_entity_id, target_entity_id, relationship_type),
    ).fetchone()

    if existing:
        if close_after:
            conn.close()
        return existing["id"]

    rel_id = _new_id()
    conn.execute(
        "INSERT INTO relationships (id, source_entity_id, target_entity_id, relationship_type, properties, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (rel_id, source_entity_id, target_entity_id, relationship_type, json.dumps(properties or {}), _now()),
    )
    conn.commit()

    if close_after:
        conn.close()
    return rel_id


def get_connections(
    entity_id: str,
    hops: int = 1,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Get entities connected to a given entity (1 or 2 hops)."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    results = []
    seen_ids = {entity_id}

    # 1-hop: direct connections
    rows = conn.execute(
        """
        SELECT r.relationship_type, e.id, e.name, e.entity_type, e.properties, 1 as hops
        FROM relationships r
        JOIN entities e ON (r.target_entity_id = e.id OR r.source_entity_id = e.id)
        WHERE (r.source_entity_id = ? OR r.target_entity_id = ?)
        AND e.id != ?
        """,
        (entity_id, entity_id, entity_id),
    ).fetchall()

    for row in rows:
        if row["id"] not in seen_ids:
            seen_ids.add(row["id"])
            results.append(dict(row))

    # 2-hop connections
    if hops >= 2:
        hop1_ids = [r["id"] for r in results]
        for hop1_id in hop1_ids:
            rows2 = conn.execute(
                """
                SELECT r.relationship_type, e.id, e.name, e.entity_type, e.properties, 2 as hops
                FROM relationships r
                JOIN entities e ON (r.target_entity_id = e.id OR r.source_entity_id = e.id)
                WHERE (r.source_entity_id = ? OR r.target_entity_id = ?)
                AND e.id != ?
                """,
                (hop1_id, hop1_id, hop1_id),
            ).fetchall()

            for row in rows2:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    results.append(dict(row))

    if close_after:
        conn.close()
    return results


# =============================================================================
# EMBEDDINGS
# =============================================================================

def _pack_embedding(embedding: list[float]) -> bytes:
    """Pack a list of floats into a compact bytes blob."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack_embedding(blob: bytes) -> list[float]:
    """Unpack a bytes blob into a list of floats."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Pure Python."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(text: str) -> Optional[list[float]]:
    """Generate embedding for text using OpenAI API. Returns None on failure."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("OPENAI_API_KEY not set, skipping embedding")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text[:8000],  # API limit safety
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


def chunk_text(text: str) -> list[str]:
    """Split text into chunks for embedding. Short texts stay whole."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    # Split at section headers (## ) or double newlines
    sections = re.split(r'\n(?=## |\n)', text)
    chunks = []
    current = ""

    for section in sections:
        if len(current) + len(section) > MAX_CHUNK_CHARS and current:
            chunks.append(current.strip())
            current = section
        else:
            current += "\n" + section if current else section

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:MAX_CHUNK_CHARS]]


def store_embedding(
    document_id: str,
    chunk_text_str: str,
    embedding: list[float],
    chunk_index: int = 0,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store an embedding for a document chunk."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    emb_id = _new_id()
    conn.execute(
        "INSERT INTO embeddings (id, document_id, chunk_index, chunk_text, embedding, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (emb_id, document_id, chunk_index, chunk_text_str, _pack_embedding(embedding), _now()),
    )
    conn.commit()

    if close_after:
        conn.close()
    return emb_id


def embed_and_store_document(
    document_id: str,
    content: str,
    conn: Optional[sqlite3.Connection] = None,
):
    """Chunk text, generate embeddings, and store them all. Fire-and-forget safe."""
    chunks = chunk_text(content)
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        if embedding:
            store_embedding(document_id, chunk, embedding, chunk_index=i, conn=conn)

    if close_after:
        conn.close()


def semantic_search(
    query: str,
    doc_type: Optional[str] = None,
    limit: int = 10,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Hybrid semantic + keyword search. Returns scored results."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    results = []

    # Semantic search via embeddings
    query_embedding = embed_text(query)
    if query_embedding:
        if doc_type:
            rows = conn.execute(
                """
                SELECT e.id, e.document_id, e.chunk_text, e.embedding,
                       d.doc_type, d.title, d.source, d.created_at
                FROM embeddings e
                JOIN documents d ON e.document_id = d.id
                WHERE d.doc_type = ?
                """,
                (doc_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT e.id, e.document_id, e.chunk_text, e.embedding,
                       d.doc_type, d.title, d.source, d.created_at
                FROM embeddings e
                JOIN documents d ON e.document_id = d.id
                """,
            ).fetchall()

        for row in rows:
            stored_emb = _unpack_embedding(row["embedding"])
            similarity = cosine_similarity(query_embedding, stored_emb)
            results.append({
                "document_id": row["document_id"],
                "chunk_text": row["chunk_text"],
                "doc_type": row["doc_type"],
                "title": row["title"],
                "source": row["source"],
                "created_at": row["created_at"],
                "similarity": similarity,
                "match_type": "semantic",
            })

    # Keyword boost: also search document content directly
    query_lower = f"%{query.lower()}%"
    if doc_type:
        kw_rows = conn.execute(
            "SELECT id, doc_type, title, content, source, created_at FROM documents "
            "WHERE doc_type = ? AND (LOWER(content) LIKE ? OR LOWER(title) LIKE ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (doc_type, query_lower, query_lower, limit * 2),
        ).fetchall()
    else:
        kw_rows = conn.execute(
            "SELECT id, doc_type, title, content, source, created_at FROM documents "
            "WHERE LOWER(content) LIKE ? OR LOWER(title) LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (query_lower, query_lower, limit * 2),
        ).fetchall()

    # Merge keyword results (boost score for keyword matches)
    seen_doc_ids = {r["document_id"] for r in results}
    for row in kw_rows:
        if row["id"] in seen_doc_ids:
            # Boost existing result
            for r in results:
                if r["document_id"] == row["id"]:
                    r["similarity"] = min(1.0, r["similarity"] + 0.15)
                    r["match_type"] = "hybrid"
                    break
        else:
            # Add keyword-only result
            content = row["content"]
            preview = content[:500] + "..." if len(content) > 500 else content
            results.append({
                "document_id": row["id"],
                "chunk_text": preview,
                "doc_type": row["doc_type"],
                "title": row["title"],
                "source": row["source"],
                "created_at": row["created_at"],
                "similarity": 0.5,  # Base score for keyword match
                "match_type": "keyword",
            })

    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)

    if close_after:
        conn.close()
    return results[:limit]


# =============================================================================
# PATTERNS & PREFERENCES
# =============================================================================

def store_pattern(
    pattern_type: str,
    description: str,
    evidence: Optional[list[str]] = None,
    confidence: float = 0.5,
    expires_at: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store a detected behavioral pattern."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    pattern_id = _new_id()
    conn.execute(
        "INSERT INTO patterns (id, pattern_type, description, evidence, confidence, detected_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (pattern_id, pattern_type, description, json.dumps(evidence or []), confidence, _now(), expires_at),
    )
    conn.commit()

    if close_after:
        conn.close()
    return pattern_id


def get_active_patterns(
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.0,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Get active patterns, optionally filtered."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    if pattern_type:
        rows = conn.execute(
            "SELECT * FROM patterns WHERE status = 'active' AND pattern_type = ? AND confidence >= ? "
            "ORDER BY confidence DESC",
            (pattern_type, min_confidence),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patterns WHERE status = 'active' AND confidence >= ? "
            "ORDER BY confidence DESC",
            (min_confidence,),
        ).fetchall()

    if close_after:
        conn.close()
    return [dict(r) for r in rows]


def store_preference(
    category: str,
    key: str,
    value: str,
    source: str = "inferred",
    confidence: float = 1.0,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store or update a preference."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    now = _now()

    # Update if exists
    existing = conn.execute(
        "SELECT id FROM preferences WHERE category = ? AND key = ?",
        (category, key),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE preferences SET value = ?, source = ?, confidence = ?, updated_at = ? WHERE id = ?",
            (value, source, confidence, now, existing["id"]),
        )
        conn.commit()
        pref_id = existing["id"]
    else:
        pref_id = _new_id()
        conn.execute(
            "INSERT INTO preferences (id, category, key, value, source, confidence, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pref_id, category, key, value, source, confidence, now, now),
        )
        conn.commit()

    if close_after:
        conn.close()
    return pref_id


def get_preferences(
    category: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """Get preferences, optionally filtered by category."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    if category:
        rows = conn.execute(
            "SELECT * FROM preferences WHERE category = ? ORDER BY key", (category,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM preferences ORDER BY category, key").fetchall()

    if close_after:
        conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# EVENTS
# =============================================================================

def store_event(
    event_type: str,
    agent: str = "",
    action: str = "",
    entity: str = "",
    metadata: Optional[dict] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Store an event in the brain DB."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    event_id = _new_id()
    conn.execute(
        "INSERT INTO events (id, event_type, agent, action, entity, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, event_type, agent, action, entity, json.dumps(metadata or {}), _now()),
    )
    conn.commit()

    if close_after:
        conn.close()
    return event_id


# =============================================================================
# INGESTION PIPELINE
# =============================================================================

EXTRACTION_PROMPT = """You are a knowledge graph extractor. Given this text, extract structured entities and relationships.

Return a JSON object with:
{{
  "entities": [
    {{"name": "...", "type": "person|project|decision|commitment|fact|preference|pattern", "properties": {{...}}}}
  ],
  "relationships": [
    {{"source": "entity_name_1", "target": "entity_name_2", "type": "mentions|relates_to|decided|committed_to|works_on|prefers"}}
  ],
  "preferences": [
    {{"category": "food|schedule|fitness|communication|work", "key": "...", "value": "..."}}
  ]
}}

Rules:
- Only extract CONCRETE facts, not transient conversation ("thanks", "ok")
- For decisions: include choice and rationale in properties
- For commitments: include deadline and context in properties
- For preferences: be specific (e.g. key="protein_target", value="154-220g")
- If nothing worth extracting, return {{"entities": [], "relationships": [], "preferences": []}}

Text:
{text}"""


def extract_from_text(text: str) -> Optional[dict]:
    """Extract entities/relationships from text. Tries CLI first, falls back to API."""
    prompt = EXTRACTION_PROMPT.format(text=text[:4000])

    # Try CLI first (uses Claude Max subscription, $0/token)
    try:
        from claude_cli import call_claude_json, cli_available
        if cli_available():
            result = call_claude_json(
                prompt,
                system_prompt="Return only valid JSON. No explanation or markdown.",
            )
            if isinstance(result, dict):
                return result
            logger.info("CLI extraction returned non-dict, falling back to API")
    except ImportError:
        pass

    # Fall back to Anthropic API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No CLI or ANTHROPIC_API_KEY available, skipping extraction")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text

        # Handle markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Extraction JSON parse error: {e}")
        return None
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None


def ingest_document(
    content: str,
    doc_type: str = "note",
    title: str = "",
    source: str = "",
    extract: bool = True,
    embed: bool = True,
    metadata: Optional[dict] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """Full ingestion pipeline: store document, extract entities, generate embeddings.

    Returns dict with doc_id and counts of extracted entities/relationships.
    """
    close_after = conn is None
    if conn is None:
        conn = get_connection()
        init_schema(conn)

    # 1. Store document
    doc_id = store_document(doc_type, content, title, source, metadata, conn=conn)

    result = {"doc_id": doc_id, "entities": 0, "relationships": 0, "preferences": 0}

    # 2. Extract entities and relationships
    if extract and len(content) > 20:  # Skip very short content
        extracted = extract_from_text(content)
        if extracted:
            entity_name_to_id = {}

            for entity_data in extracted.get("entities", []):
                name = entity_data.get("name", "")
                etype = entity_data.get("type", "fact")
                props = entity_data.get("properties", {})
                if name:
                    eid = store_entity(name, etype, props, conn=conn)
                    entity_name_to_id[name] = eid
                    result["entities"] += 1

            for rel_data in extracted.get("relationships", []):
                src_name = rel_data.get("source", "")
                tgt_name = rel_data.get("target", "")
                rtype = rel_data.get("type", "relates_to")
                src_id = entity_name_to_id.get(src_name)
                tgt_id = entity_name_to_id.get(tgt_name)
                if src_id and tgt_id:
                    store_relationship(src_id, tgt_id, rtype, conn=conn)
                    result["relationships"] += 1

            for pref_data in extracted.get("preferences", []):
                cat = pref_data.get("category", "")
                key = pref_data.get("key", "")
                val = pref_data.get("value", "")
                if cat and key and val:
                    store_preference(cat, key, val, source="inferred", conn=conn)
                    result["preferences"] += 1

    # 3. Generate and store embeddings
    if embed:
        embed_and_store_document(doc_id, content, conn=conn)

    if close_after:
        conn.close()
    return result


def ingest_conversation(
    user_message: str,
    assistant_response: str,
    chat_id: int = 0,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """Ingest a conversation turn into the brain."""
    combined = f"User: {user_message}\n\nAssistant: {assistant_response}"
    return ingest_document(
        content=combined,
        doc_type="conversation",
        title=user_message[:100],
        source=f"chat_{chat_id}",
        conn=conn,
    )


# =============================================================================
# PATTERN DETECTION
# =============================================================================

PATTERN_DETECTION_PROMPT = """Analyze these recent documents from a personal productivity system and detect behavioral patterns.

Look for:
1. Recurring behaviors (positive or negative)
2. Food/nutrition patterns
3. Productivity patterns (task completion, time management)
4. Mood and energy correlations
5. Sleep patterns

Return a JSON array of detected patterns:
[
  {{
    "type": "behavioral|food|productivity|mood|sleep",
    "description": "Clear, specific pattern description",
    "confidence": 0.0-1.0,
    "evidence_summary": "Brief summary of supporting evidence"
  }}
]

If no clear patterns, return [].

Recent documents:
{documents}"""


def detect_patterns(days: int = 7, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    """Run pattern detection on recent documents using Haiku."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = conn.execute(
        "SELECT title, content, doc_type, created_at FROM documents WHERE created_at >= ? ORDER BY created_at",
        (cutoff,),
    ).fetchall()

    if not rows:
        if close_after:
            conn.close()
        return []

    # Build document summary for analysis
    doc_summaries = []
    for row in rows:
        content = row["content"][:500]  # Truncate each doc
        doc_summaries.append(f"[{row['doc_type']}] {row['title']}: {content}")

    documents_text = "\n---\n".join(doc_summaries[:50])  # Cap at 50 docs

    prompt = PATTERN_DETECTION_PROMPT.format(documents=documents_text)
    patterns = None

    # Try CLI first (uses Claude Max subscription, $0/token)
    try:
        from claude_cli import call_claude_json, cli_available
        if cli_available():
            result = call_claude_json(
                prompt,
                system_prompt="Return only a valid JSON array. No explanation or markdown.",
            )
            if isinstance(result, list):
                patterns = result
            else:
                logger.info("CLI pattern detection returned non-list, falling back to API")
    except ImportError:
        pass

    # Fall back to Anthropic API
    if patterns is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            if close_after:
                conn.close()
            return []

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            patterns = json.loads(raw.strip())
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            if close_after:
                conn.close()
            return []

    if not isinstance(patterns, list):
        if close_after:
            conn.close()
        return []

    stored = []
    for p in patterns:
        pattern_id = store_pattern(
            pattern_type=p.get("type", "behavioral"),
            description=p.get("description", ""),
            confidence=p.get("confidence", 0.5),
            conn=conn,
        )
        stored.append({"id": pattern_id, **p})

        # Auto-promote high-confidence patterns to preferences
        if p.get("confidence", 0) >= 0.8 and p.get("type") in ("food", "fitness", "schedule"):
            store_preference(
                category=p["type"],
                key=f"pattern_{pattern_id[:8]}",
                value=p.get("description", ""),
                source="inferred",
                confidence=p.get("confidence", 0.8),
                conn=conn,
            )

    if close_after:
        conn.close()
    return stored


# =============================================================================
# BRAIN CONTEXT (for system prompt injection)
# =============================================================================

def get_brain_context(
    user_message: str = "",
    limit_patterns: int = 5,
    limit_preferences: int = 10,
    limit_memories: int = 5,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Build brain-enriched context string for injection into system prompt."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    sections = []

    # Active patterns
    patterns = get_active_patterns(min_confidence=0.5, conn=conn)[:limit_patterns]
    if patterns:
        lines = ["DETECTED PATTERNS:"]
        for p in patterns:
            lines.append(f"- [{p['pattern_type']}] {p['description']} (confidence: {p['confidence']:.0%})")
        sections.append("\n".join(lines))

    # Preferences
    prefs = get_preferences(conn=conn)[:limit_preferences]
    if prefs:
        lines = ["KNOWN PREFERENCES:"]
        for p in prefs:
            lines.append(f"- [{p['category']}] {p['key']}: {p['value']}")
        sections.append("\n".join(lines))

    # Relevant memories (semantic search if we have a user message)
    if user_message:
        memories = semantic_search(user_message, limit=limit_memories, conn=conn)
        if memories:
            lines = ["RELEVANT MEMORIES:"]
            for m in memories:
                preview = m["chunk_text"][:200]
                lines.append(f"- [{m['doc_type']}] {m.get('title', '')}: {preview}")
            sections.append("\n".join(lines))

    # Overdue commitments
    commitment_entities = find_entities(entity_type="commitment", conn=conn)
    overdue = []
    now = datetime.now().isoformat()[:10]
    for c in commitment_entities:
        props = json.loads(c.get("properties", "{}")) if isinstance(c.get("properties"), str) else c.get("properties", {})
        deadline = props.get("deadline", "")
        status = props.get("status", "open")
        if deadline and deadline < now and status == "open":
            overdue.append(f"- {c['name']} (deadline: {deadline})")

    if overdue:
        sections.append("OVERDUE COMMITMENTS:\n" + "\n".join(overdue))

    if close_after:
        conn.close()

    return "\n\n".join(sections) if sections else ""


# =============================================================================
# STATS
# =============================================================================

def get_brain_stats(conn: Optional[sqlite3.Connection] = None) -> dict:
    """Get counts of all brain DB tables."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    stats = {}
    for table in ["documents", "entities", "relationships", "embeddings", "patterns", "preferences", "events"]:
        try:
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            stats[table] = row["c"]
        except sqlite3.OperationalError:
            stats[table] = 0

    if close_after:
        conn.close()
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Brain DB CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize the database schema")
    sub.add_parser("stats", help="Show database stats")

    search_p = sub.add_parser("search", help="Semantic search")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--type", default=None, help="Filter by doc_type")
    search_p.add_argument("--limit", type=int, default=5, help="Max results")

    ingest_p = sub.add_parser("ingest", help="Ingest text")
    ingest_p.add_argument("text", help="Text to ingest")
    ingest_p.add_argument("--type", default="note", help="Document type")
    ingest_p.add_argument("--title", default="", help="Document title")

    sub.add_parser("patterns", help="Run pattern detection")

    args = parser.parse_args()

    if args.command == "init":
        conn = get_connection()
        init_schema(conn)
        conn.close()
        print("Brain DB initialized at", DB_PATH)

    elif args.command == "stats":
        stats = get_brain_stats()
        for table, count in stats.items():
            print(f"  {table}: {count}")

    elif args.command == "search":
        results = semantic_search(args.query, doc_type=args.type, limit=args.limit)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['doc_type']}] {r.get('title', 'Untitled')} (score: {r['similarity']:.3f})")
            print(f"   {r['chunk_text'][:200]}")

    elif args.command == "ingest":
        result = ingest_document(args.text, doc_type=args.type, title=args.title)
        print(f"Ingested: doc_id={result['doc_id']}, entities={result['entities']}, "
              f"relationships={result['relationships']}, preferences={result['preferences']}")

    elif args.command == "patterns":
        patterns = detect_patterns()
        for p in patterns:
            print(f"- [{p.get('type')}] {p.get('description')} (confidence: {p.get('confidence', 0):.0%})")

    else:
        parser.print_help()

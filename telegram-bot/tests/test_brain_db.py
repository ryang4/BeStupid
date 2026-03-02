"""
Tests for scripts/brain_db.py — second brain SQLite module.

Covers schema init, CRUD, keyword search, embeddings, cosine similarity,
ingestion pipeline, patterns, preferences, and brain context generation.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is importable
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import brain_db


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary brain.db for each test."""
    db_path = tmp_path / "brain.db"
    with patch.object(brain_db, "DB_PATH", db_path):
        with patch.object(brain_db, "MEMORY_ROOT", tmp_path):
            conn = brain_db.get_connection()
            brain_db.init_schema(conn)
            yield conn
            conn.close()


# =============================================================================
# SCHEMA
# =============================================================================


class TestSchema:
    def test_init_schema_creates_tables(self, db_conn):
        tables = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "documents" in table_names
        assert "entities" in table_names
        assert "relationships" in table_names
        assert "embeddings" in table_names
        assert "patterns" in table_names
        assert "preferences" in table_names
        assert "events" in table_names

    def test_init_schema_idempotent(self, db_conn):
        """Running init_schema twice should not error."""
        brain_db.init_schema(db_conn)
        brain_db.init_schema(db_conn)
        row = db_conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()
        assert row["c"] == 0


# =============================================================================
# DOCUMENTS CRUD
# =============================================================================


class TestDocuments:
    def test_store_and_get_document(self, db_conn):
        doc_id = brain_db.store_document(
            doc_type="note",
            content="Test content here",
            title="Test Note",
            source="test",
            conn=db_conn,
        )
        assert doc_id
        assert len(doc_id) > 10  # ULID length

        doc = brain_db.get_document(doc_id, conn=db_conn)
        assert doc is not None
        assert doc["title"] == "Test Note"
        assert doc["content"] == "Test content here"
        assert doc["doc_type"] == "note"

    def test_get_nonexistent_document(self, db_conn):
        doc = brain_db.get_document("nonexistent", conn=db_conn)
        assert doc is None

    def test_search_documents_keyword(self, db_conn):
        brain_db.store_document("note", "I love swimming in the morning", title="Swim", conn=db_conn)
        brain_db.store_document("note", "Running at night is great", title="Run", conn=db_conn)

        results = brain_db.search_documents_keyword("swimming", conn=db_conn)
        assert len(results) == 1
        assert results[0]["title"] == "Swim"

    def test_search_documents_keyword_by_type(self, db_conn):
        brain_db.store_document("note", "Protein target is 180g", conn=db_conn)
        brain_db.store_document("log_entry", "Protein intake today: 150g", conn=db_conn)

        results = brain_db.search_documents_keyword("protein", doc_type="log_entry", conn=db_conn)
        assert len(results) == 1
        assert results[0]["doc_type"] == "log_entry"

    def test_get_recent_documents(self, db_conn):
        for i in range(5):
            brain_db.store_document("note", f"Note {i}", title=f"Note {i}", conn=db_conn)

        results = brain_db.get_recent_documents(limit=3, conn=db_conn)
        assert len(results) == 3

    def test_get_recent_documents_by_type(self, db_conn):
        brain_db.store_document("note", "A note", conn=db_conn)
        brain_db.store_document("conversation", "A chat", conn=db_conn)

        results = brain_db.get_recent_documents(doc_type="conversation", conn=db_conn)
        assert len(results) == 1
        assert results[0]["doc_type"] == "conversation"


# =============================================================================
# ENTITIES CRUD
# =============================================================================


class TestEntities:
    def test_store_and_find_entity(self, db_conn):
        entity_id = brain_db.store_entity(
            "John Smith", "person", {"role": "PM"}, conn=db_conn,
        )
        assert entity_id

        entities = brain_db.find_entities(name="john", conn=db_conn)
        assert len(entities) == 1
        assert entities[0]["name"] == "John Smith"
        props = json.loads(entities[0]["properties"])
        assert props["role"] == "PM"

    def test_store_entity_upserts_on_duplicate(self, db_conn):
        id1 = brain_db.store_entity("John", "person", {"role": "PM"}, conn=db_conn)
        id2 = brain_db.store_entity("John", "person", {"company": "Acme"}, conn=db_conn)

        # Same entity, should reuse ID
        assert id1 == id2

        entity = brain_db.get_entity(id1, conn=db_conn)
        props = json.loads(entity["properties"])
        # Merged properties
        assert props["role"] == "PM"
        assert props["company"] == "Acme"

    def test_find_entities_by_type(self, db_conn):
        brain_db.store_entity("Swimming", "decision", {"choice": "swim 3x/week"}, conn=db_conn)
        brain_db.store_entity("John", "person", {}, conn=db_conn)

        decisions = brain_db.find_entities(entity_type="decision", conn=db_conn)
        assert len(decisions) == 1
        assert decisions[0]["name"] == "Swimming"

    def test_get_entity_by_id(self, db_conn):
        eid = brain_db.store_entity("Test Entity", "fact", {"key": "val"}, conn=db_conn)
        entity = brain_db.get_entity(eid, conn=db_conn)
        assert entity is not None
        assert entity["name"] == "Test Entity"

    def test_get_nonexistent_entity(self, db_conn):
        entity = brain_db.get_entity("nonexistent", conn=db_conn)
        assert entity is None


# =============================================================================
# RELATIONSHIPS
# =============================================================================


class TestRelationships:
    def test_store_and_get_connections(self, db_conn):
        e1 = brain_db.store_entity("Ryan", "person", conn=db_conn)
        e2 = brain_db.store_entity("BeStupid", "project", conn=db_conn)

        rel_id = brain_db.store_relationship(e1, e2, "works_on", conn=db_conn)
        assert rel_id

        connections = brain_db.get_connections(e1, conn=db_conn)
        assert len(connections) == 1
        assert connections[0]["name"] == "BeStupid"
        assert connections[0]["relationship_type"] == "works_on"

    def test_relationship_deduplication(self, db_conn):
        e1 = brain_db.store_entity("A", "fact", conn=db_conn)
        e2 = brain_db.store_entity("B", "fact", conn=db_conn)

        id1 = brain_db.store_relationship(e1, e2, "relates_to", conn=db_conn)
        id2 = brain_db.store_relationship(e1, e2, "relates_to", conn=db_conn)
        assert id1 == id2

    def test_two_hop_connections(self, db_conn):
        e1 = brain_db.store_entity("A", "person", conn=db_conn)
        e2 = brain_db.store_entity("B", "project", conn=db_conn)
        e3 = brain_db.store_entity("C", "decision", conn=db_conn)

        brain_db.store_relationship(e1, e2, "works_on", conn=db_conn)
        brain_db.store_relationship(e2, e3, "decided", conn=db_conn)

        # 1-hop from A: should find B only
        one_hop = brain_db.get_connections(e1, hops=1, conn=db_conn)
        assert len(one_hop) == 1
        assert one_hop[0]["name"] == "B"

        # 2-hop from A: should find B and C
        two_hop = brain_db.get_connections(e1, hops=2, conn=db_conn)
        assert len(two_hop) == 2
        names = {c["name"] for c in two_hop}
        assert names == {"B", "C"}


# =============================================================================
# EMBEDDINGS
# =============================================================================


class TestEmbeddings:
    def test_pack_unpack_roundtrip(self):
        original = [0.1, 0.2, 0.3, -0.5, 1.0]
        packed = brain_db._pack_embedding(original)
        unpacked = brain_db._unpack_embedding(packed)
        assert len(unpacked) == len(original)
        for a, b in zip(original, unpacked):
            assert abs(a - b) < 1e-6

    def test_cosine_similarity_identical(self):
        vec = [1.0, 2.0, 3.0]
        assert abs(brain_db.cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(brain_db.cosine_similarity(a, b)) < 1e-6

    def test_cosine_similarity_opposite(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(brain_db.cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert brain_db.cosine_similarity(a, b) == 0.0

    def test_chunk_text_short(self):
        text = "Short text"
        chunks = brain_db.chunk_text(text)
        assert chunks == ["Short text"]

    def test_chunk_text_long(self):
        # Create a long text with sections
        sections = [f"## Section {i}\n{'x' * 500}" for i in range(10)]
        text = "\n".join(sections)
        chunks = brain_db.chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= brain_db.MAX_CHUNK_CHARS + 100  # Allow some slop

    def test_store_embedding(self, db_conn):
        doc_id = brain_db.store_document("note", "Test", conn=db_conn)
        embedding = [0.1] * 10
        emb_id = brain_db.store_embedding(doc_id, "Test", embedding, conn=db_conn)
        assert emb_id

        row = db_conn.execute("SELECT * FROM embeddings WHERE id = ?", (emb_id,)).fetchone()
        assert row is not None
        stored = brain_db._unpack_embedding(row["embedding"])
        assert len(stored) == 10


# =============================================================================
# PATTERNS & PREFERENCES
# =============================================================================


class TestPatternsPreferences:
    def test_store_and_get_pattern(self, db_conn):
        pid = brain_db.store_pattern(
            "food", "Eats Cheez-Its daily", confidence=0.85, conn=db_conn,
        )
        assert pid

        patterns = brain_db.get_active_patterns(conn=db_conn)
        assert len(patterns) == 1
        assert patterns[0]["description"] == "Eats Cheez-Its daily"
        assert patterns[0]["confidence"] == 0.85

    def test_get_patterns_filtered_by_type(self, db_conn):
        brain_db.store_pattern("food", "Pattern A", confidence=0.7, conn=db_conn)
        brain_db.store_pattern("mood", "Pattern B", confidence=0.8, conn=db_conn)

        food = brain_db.get_active_patterns(pattern_type="food", conn=db_conn)
        assert len(food) == 1
        assert food[0]["description"] == "Pattern A"

    def test_get_patterns_min_confidence(self, db_conn):
        brain_db.store_pattern("food", "Low conf", confidence=0.3, conn=db_conn)
        brain_db.store_pattern("food", "High conf", confidence=0.9, conn=db_conn)

        high = brain_db.get_active_patterns(min_confidence=0.5, conn=db_conn)
        assert len(high) == 1
        assert high[0]["description"] == "High conf"

    def test_store_and_get_preference(self, db_conn):
        pid = brain_db.store_preference(
            "food", "protein_target", "154-220g", source="explicit", conn=db_conn,
        )
        assert pid

        prefs = brain_db.get_preferences(category="food", conn=db_conn)
        assert len(prefs) == 1
        assert prefs[0]["key"] == "protein_target"
        assert prefs[0]["value"] == "154-220g"

    def test_preference_upsert(self, db_conn):
        brain_db.store_preference("food", "protein_target", "150g", conn=db_conn)
        brain_db.store_preference("food", "protein_target", "180g", conn=db_conn)

        prefs = brain_db.get_preferences(category="food", conn=db_conn)
        assert len(prefs) == 1
        assert prefs[0]["value"] == "180g"


# =============================================================================
# EVENTS
# =============================================================================


class TestEvents:
    def test_store_event(self, db_conn):
        eid = brain_db.store_event(
            "extraction_complete", agent="extractor", action="extracted 3 ops", conn=db_conn,
        )
        assert eid

        row = db_conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
        assert row["event_type"] == "extraction_complete"
        assert row["agent"] == "extractor"


# =============================================================================
# INGESTION PIPELINE
# =============================================================================


class TestIngestion:
    def test_ingest_document_no_extract(self, db_conn):
        """Ingest with extraction disabled — just stores doc."""
        with patch.object(brain_db, "DB_PATH", db_conn.execute("PRAGMA database_list").fetchone()[2] or ""):
            result = brain_db.ingest_document(
                content="Test note about swimming",
                doc_type="note",
                title="Swim Note",
                extract=False,
                embed=False,
                conn=db_conn,
            )

        assert result["doc_id"]
        assert result["entities"] == 0

        doc = brain_db.get_document(result["doc_id"], conn=db_conn)
        assert doc["title"] == "Swim Note"

    def test_ingest_document_with_mock_extraction(self, db_conn):
        """Ingest with mocked extraction response."""
        mock_extracted = {
            "entities": [
                {"name": "Swimming", "type": "decision", "properties": {"choice": "swim 3x/week"}},
            ],
            "relationships": [],
            "preferences": [
                {"category": "fitness", "key": "swim_frequency", "value": "3x/week"},
            ],
        }

        with patch.object(brain_db, "extract_from_text", return_value=mock_extracted):
            result = brain_db.ingest_document(
                content="I decided to swim three times a week for cardio",
                doc_type="note",
                extract=True,
                embed=False,
                conn=db_conn,
            )

        assert result["entities"] == 1
        assert result["preferences"] == 1

        entities = brain_db.find_entities(name="Swimming", conn=db_conn)
        assert len(entities) == 1

        prefs = brain_db.get_preferences(category="fitness", conn=db_conn)
        assert len(prefs) == 1
        assert prefs[0]["value"] == "3x/week"

    def test_ingest_conversation(self, db_conn):
        """Ingest a conversation turn."""
        with patch.object(brain_db, "extract_from_text", return_value={"entities": [], "relationships": [], "preferences": []}):
            result = brain_db.ingest_conversation(
                user_message="What's my protein target?",
                assistant_response="Your protein target is 154-220g per day.",
                chat_id=12345,
                conn=db_conn,
            )

        assert result["doc_id"]
        doc = brain_db.get_document(result["doc_id"], conn=db_conn)
        assert doc["doc_type"] == "conversation"
        assert "protein target" in doc["content"]


# =============================================================================
# BRAIN CONTEXT
# =============================================================================


class TestBrainContext:
    def test_brain_context_with_patterns(self, db_conn):
        brain_db.store_pattern("food", "Eats too many snacks", confidence=0.8, conn=db_conn)
        brain_db.store_preference("food", "protein_target", "180g", conn=db_conn)

        context = brain_db.get_brain_context(conn=db_conn)
        assert "DETECTED PATTERNS" in context
        assert "snacks" in context
        assert "KNOWN PREFERENCES" in context
        assert "protein_target" in context

    def test_brain_context_empty_db(self, db_conn):
        context = brain_db.get_brain_context(conn=db_conn)
        assert context == ""

    def test_brain_context_overdue_commitments(self, db_conn):
        brain_db.store_entity(
            "Call John", "commitment",
            {"deadline": "2020-01-01", "status": "open"},
            conn=db_conn,
        )

        context = brain_db.get_brain_context(conn=db_conn)
        assert "OVERDUE COMMITMENTS" in context
        assert "Call John" in context


# =============================================================================
# STATS
# =============================================================================


class TestStats:
    def test_brain_stats_empty(self, db_conn):
        stats = brain_db.get_brain_stats(conn=db_conn)
        assert stats["documents"] == 0
        assert stats["entities"] == 0

    def test_brain_stats_after_inserts(self, db_conn):
        brain_db.store_document("note", "Test", conn=db_conn)
        brain_db.store_entity("Foo", "fact", conn=db_conn)

        stats = brain_db.get_brain_stats(conn=db_conn)
        assert stats["documents"] == 1
        assert stats["entities"] == 1


# =============================================================================
# SEMANTIC SEARCH (keyword-only path, since we mock embeddings)
# =============================================================================


class TestSemanticSearch:
    def test_keyword_search_fallback(self, db_conn):
        """Without OPENAI_API_KEY, semantic search falls back to keyword-only."""
        brain_db.store_document("note", "Swimming is great for cardio", title="Swimming", conn=db_conn)
        brain_db.store_document("note", "Running burns more calories", title="Running", conn=db_conn)

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            results = brain_db.semantic_search("swimming", conn=db_conn)

        assert len(results) >= 1
        assert results[0]["title"] == "Swimming"

    def test_semantic_search_with_mock_embeddings(self, db_conn):
        """Test full semantic path with mocked embeddings."""
        doc_id = brain_db.store_document("note", "Swimming helps cardio", title="Swim", conn=db_conn)

        # Store a fake embedding
        fake_emb = [0.1] * brain_db.EMBEDDING_DIM
        brain_db.store_embedding(doc_id, "Swimming helps cardio", fake_emb, conn=db_conn)

        # Mock embed_text to return a similar vector
        with patch.object(brain_db, "embed_text", return_value=fake_emb):
            results = brain_db.semantic_search("cardio exercise", conn=db_conn)

        assert len(results) >= 1
        # The stored doc should match since we return the same embedding
        assert any(r["document_id"] == doc_id for r in results)

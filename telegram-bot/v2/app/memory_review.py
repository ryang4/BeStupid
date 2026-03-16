from __future__ import annotations

import re

from v2.domain.models import MemoryCandidateRecord
from v2.infra.sqlite_state_store import SQLiteStateStore


class MemoryReviewServiceImpl:
    """Heuristic memory extraction with explicit review-before-save."""

    def __init__(self, store: SQLiteStateStore):
        self.store = store

    def extract_candidates(self, chat_id: int, turn_id: str, text: str) -> list[MemoryCandidateRecord]:
        candidates = []
        source = text.strip()
        lowered = source.lower()
        if not source:
            return []

        remember_match = re.search(r"\bremember that (.+)", source, re.IGNORECASE)
        if remember_match:
            fact = remember_match.group(1).strip().rstrip(".")
            candidates.append(
                {
                    "kind": "fact",
                    "payload": {"fact": fact},
                    "confidence": 0.85,
                    "reason": "Explicit remember-that statement.",
                }
            )

        prefer_match = re.search(r"\bi prefer (.+)", source, re.IGNORECASE)
        if prefer_match:
            statement = prefer_match.group(1).strip().rstrip(".")
            candidates.append(
                {
                    "kind": "preference",
                    "payload": {"subject": "general", "statement": statement},
                    "confidence": 0.8,
                    "reason": "Explicit preference statement.",
                }
            )

        dislike_match = re.search(r"\bi (?:do not|don't) like (.+)", source, re.IGNORECASE)
        if dislike_match:
            statement = f"does not like {dislike_match.group(1).strip().rstrip('.')}"
            candidates.append(
                {
                    "kind": "preference",
                    "payload": {"subject": "general", "statement": statement},
                    "confidence": 0.78,
                    "reason": "Explicit negative preference statement.",
                }
            )

        relationship_match = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) is my ([^.]+)", source)
        if relationship_match and "timezone" not in lowered:
            candidates.append(
                {
                    "kind": "relationship",
                    "payload": {
                        "name": relationship_match.group(1).strip(),
                        "role": relationship_match.group(2).strip().rstrip("."),
                    },
                    "confidence": 0.75,
                    "reason": "Explicit relationship statement.",
                }
            )

        commitment_match = re.search(r"\bI committed to (.+)", source, re.IGNORECASE)
        if commitment_match:
            title = commitment_match.group(1).strip().rstrip(".")
            candidates.append(
                {
                    "kind": "commitment",
                    "payload": {"title": title, "status": "open"},
                    "confidence": 0.72,
                    "reason": "Explicit commitment statement.",
                }
            )

        return self.store.create_memory_candidates(chat_id, turn_id, candidates)

    def review_candidate(
        self,
        chat_id: int,
        candidate_id: str,
        action: str,
        edited_payload: dict | None = None,
    ) -> dict | None:
        return self.store.review_memory_candidate(chat_id, candidate_id, action, edited_payload=edited_payload)

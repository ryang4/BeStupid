"""Shared token estimation utilities."""


def estimate_tokens(text: str) -> int:
    """Estimate token count. Uses 3.2 chars/token (compromise between English ~4 and JSON/code ~3)."""
    return max(1, int(len(text) / 3.2))

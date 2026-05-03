"""Helpers to suggest transaction ID remapping for transaction_overrides.json.

The workflow is intentionally manual:
- keep legacy override entries keyed by old transaction IDs
- store an optional `_row` hint in each entry
- after ID reset/regeneration, use these helpers to propose old->new ID pairs
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from models import Transaction


@dataclass
class MatchCandidate:
    transaction_id: str
    score: float
    source_line_number: Optional[int]
    source_row_text: str


@dataclass
class RemapSuggestion:
    old_id: str
    status: str
    new_id: Optional[str]
    score: Optional[float]
    message: str
    candidates: list[MatchCandidate]


def normalize_row_text(value: str) -> str:
    """Normalize row text for resilient comparison."""
    normalized = (value or "").strip().upper()
    normalized = normalized.replace('"', "")
    normalized = " ".join(normalized.split())
    return normalized


def find_candidates(
    row_hint: str,
    transactions: list[Transaction],
    limit: int = 3,
    min_score: float = 0.45,
) -> list[MatchCandidate]:
    """Return best matching transaction rows for a row hint."""
    hint = normalize_row_text(row_hint)
    if not hint:
        return []

    scored: list[MatchCandidate] = []
    for txn in transactions:
        row = normalize_row_text(txn.source_row_text)
        if not row:
            continue

        if row == hint:
            score = 1.0
        elif hint in row or row in hint:
            score = 0.98
        else:
            score = SequenceMatcher(a=hint, b=row).ratio()

        if score >= min_score:
            scored.append(
                MatchCandidate(
                    transaction_id=txn.transaction_id,
                    score=score,
                    source_line_number=txn.source_line_number,
                    source_row_text=txn.source_row_text,
                )
            )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:limit]


def build_remap_suggestions(
    overrides: dict,
    transactions: list[Transaction],
    candidate_limit: int = 3,
) -> list[RemapSuggestion]:
    """Build remap suggestions for override entries.

    Status values:
    - id_exists: old ID is still present
    - remap_exact: exact row match to a different current ID
    - remap_fuzzy: likely match based on similarity
    - ambiguous: multiple similar candidates, manual choice required
    - missing_row_hint: override has no `_row` hint
    - no_match: no candidate could be found
    """
    current_ids = {t.transaction_id for t in transactions}
    suggestions: list[RemapSuggestion] = []

    for old_id in sorted(overrides.keys()):
        entry = overrides.get(old_id) or {}
        row_hint = entry.get("_row")

        if old_id in current_ids:
            suggestions.append(
                RemapSuggestion(
                    old_id=old_id,
                    status="id_exists",
                    new_id=old_id,
                    score=1.0,
                    message="ID is still present; no remap needed.",
                    candidates=[],
                )
            )
            continue

        if not isinstance(row_hint, str) or not row_hint.strip():
            suggestions.append(
                RemapSuggestion(
                    old_id=old_id,
                    status="missing_row_hint",
                    new_id=None,
                    score=None,
                    message="No '_row' hint available in override entry.",
                    candidates=[],
                )
            )
            continue

        candidates = find_candidates(row_hint, transactions, limit=candidate_limit)
        if not candidates:
            suggestions.append(
                RemapSuggestion(
                    old_id=old_id,
                    status="no_match",
                    new_id=None,
                    score=None,
                    message="No matching input row found.",
                    candidates=[],
                )
            )
            continue

        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        is_ambiguous = second is not None and (best.score - second.score) < 0.03

        if best.score >= 0.999:
            status = "remap_exact"
            message = "Exact row match found."
        elif is_ambiguous:
            status = "ambiguous"
            message = "Multiple similar candidates found; choose manually."
        else:
            status = "remap_fuzzy"
            message = "Likely row match found (fuzzy)."

        suggestions.append(
            RemapSuggestion(
                old_id=old_id,
                status=status,
                new_id=best.transaction_id,
                score=best.score,
                message=message,
                candidates=candidates,
            )
        )

    return suggestions

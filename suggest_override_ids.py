#!/usr/bin/env python3
"""Suggest transaction_overrides ID remapping after ID resets/regeneration.

Usage:
    uv run python suggest_override_ids.py <run_dir>

Example:
    uv run python suggest_override_ids.py example
    uv run python suggest_override_ids.py data/private/dev --limit 5
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from import_handler import ImportHandler
from override_id_remap import build_remap_suggestions
from transaction_id_registry import TransactionIdRegistry


def _resolve_run_directory(arg: str) -> Path:
    direct = Path(arg)
    if direct.exists() and direct.is_dir():
        return direct

    under_data = Path("data") / arg
    if under_data.exists() and under_data.is_dir():
        return under_data

    raise FileNotFoundError(
        f"Run directory not found: '{arg}' (also checked '{under_data}')"
    )


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Overrides file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("transaction_overrides.json must contain a JSON object.")
    return data


def _load_transactions_with_ids(run_dir: Path, debug: bool = False):
    input_dir = run_dir / "input"
    metadata_dir = run_dir / "metadata"
    registry_path = metadata_dir / "transaction_id_registry.json"

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    input_files = sorted(input_dir.glob("*.csv"))
    if not input_files:
        raise FileNotFoundError(f"No CSV files found in: {input_dir}")

    all_transactions = []
    for input_csv in input_files:
        txns = ImportHandler.load_csv(str(input_csv), debug=debug)
        all_transactions.extend(txns)

    id_registry = TransactionIdRegistry(registry_path)
    id_registry.assign_batch(all_transactions)
    return all_transactions


def _print_suggestions(suggestions):
    print("\nID remap suggestions")
    print("=" * 80)
    for suggestion in suggestions:
        score_text = f"{suggestion.score:.3f}" if suggestion.score is not None else "-"
        new_id = suggestion.new_id or "-"
        print(
            f"{suggestion.old_id:>10} | {suggestion.status:<16} | {new_id:<10} | "
            f"score={score_text} | {suggestion.message}"
        )

        if suggestion.status in {"ambiguous", "remap_fuzzy", "no_match"} and suggestion.candidates:
            for idx, candidate in enumerate(suggestion.candidates, start=1):
                line = candidate.source_line_number if candidate.source_line_number is not None else "?"
                row_excerpt = candidate.source_row_text[:120]
                print(
                    f"            cand#{idx}: {candidate.transaction_id} "
                    f"(score={candidate.score:.3f}, line={line}) {row_excerpt}"
                )


def _print_patch_template(suggestions):
    print("\nSuggested manual updates (old_id -> new_id)")
    print("=" * 80)
    for s in suggestions:
        if s.status in {"remap_exact", "remap_fuzzy"} and s.new_id:
            print(f"{s.old_id} -> {s.new_id}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Suggest old->new transaction ID remapping for transaction_overrides.json"
    )
    parser.add_argument("run_dir", help="Dataset directory or shorthand under data/")
    parser.add_argument("--limit", type=int, default=3, help="Max candidate rows per entry")
    parser.add_argument("--debug", action="store_true", help="Enable verbose CSV import debug")
    args = parser.parse_args(argv)

    try:
        run_dir = _resolve_run_directory(args.run_dir)
        overrides = _load_overrides(run_dir / "transaction_overrides.json")
        transactions = _load_transactions_with_ids(run_dir, debug=args.debug)
        suggestions = build_remap_suggestions(
            overrides,
            transactions,
            candidate_limit=max(1, args.limit),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ {e}")
        return 1

    print(f"Dataset: {run_dir}")
    print(f"Override entries: {len(overrides)}")
    print(f"Input transactions scanned: {len(transactions)}")
    _print_suggestions(suggestions)
    _print_patch_template(suggestions)
    return 0


if __name__ == "__main__":
    sys.exit(main())

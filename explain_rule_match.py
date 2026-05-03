#!/usr/bin/env python3
"""Explain rule matching decisions for a single transaction."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from categorize_transactions import _resolve_run_directory
from import_handler import ImportHandler
from rule_engine import RuleEngine
from transaction_id_registry import TransactionIdRegistry
from transaction_overrides import load_overrides_if_present


def _resolve_rules(run_dir: Path) -> tuple[str, Optional[str], Optional[str]]:
    """Resolve base rules, overlay path, and overrides path for a run directory."""
    rules_file = run_dir / "rules.json"
    if not rules_file.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_file}")

    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    base_name = rules_data.get("base")
    if base_name:
        base_rules_path = str(Path("data") / base_name / "rules.json")
        overlay_path: Optional[str] = str(rules_file)
    else:
        base_rules_path = str(rules_file)
        overlay_path = None

    overrides_file = run_dir / "transaction_overrides.json"
    overrides_path = str(overrides_file) if overrides_file.exists() else None
    return base_rules_path, overlay_path, overrides_path


def _build_transactions_index(run_dir: Path) -> dict:
    """Load all input transactions, assign IDs, and return transaction lookup indexes."""
    input_dir = run_dir / "input"
    metadata_dir = run_dir / "metadata"
    registry_path = metadata_dir / "transaction_id_registry.json"

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    input_files = sorted(input_dir.glob("*.csv"))
    if not input_files:
        raise FileNotFoundError(f"No CSV files found in: {input_dir}")

    id_registry = TransactionIdRegistry(registry_path)

    by_id = {}
    by_file_and_line = {}
    all_transactions = []

    for input_csv in input_files:
        transactions = ImportHandler.load_csv(str(input_csv), debug=False)
        id_registry.assign_batch(transactions)

        per_file_line = {}
        for txn in transactions:
            by_id[txn.transaction_id] = (input_csv, txn)
            if txn.source_line_number is not None:
                per_file_line[txn.source_line_number] = txn
            all_transactions.append((input_csv, txn))

        by_file_and_line[input_csv.name] = per_file_line

    return {
        "by_id": by_id,
        "by_file_and_line": by_file_and_line,
        "all_transactions": all_transactions,
        "input_files": [p.name for p in input_files],
    }


def _select_transaction(
    index_data: dict,
    transaction_id: Optional[str],
    line_number: Optional[int],
    input_file: Optional[str],
):
    """Select one transaction by ID or by source line (optionally scoped to a file)."""
    if bool(transaction_id) == bool(line_number):
        raise ValueError("Specify exactly one selector: --transaction-id or --line-number")

    if transaction_id:
        selected = index_data["by_id"].get(transaction_id)
        if not selected:
            raise ValueError(f"Transaction ID not found: {transaction_id}")
        return selected

    if input_file:
        file_map = index_data["by_file_and_line"].get(input_file)
        if file_map is None:
            raise ValueError(
                f"Unknown input file '{input_file}'. Available: {index_data['input_files']}"
            )
        txn = file_map.get(line_number)
        if not txn:
            raise ValueError(
                f"No transaction found in file '{input_file}' at source line {line_number}"
            )
        return Path("input") / input_file, txn

    matches = []
    for file_name, line_map in index_data["by_file_and_line"].items():
        txn = line_map.get(line_number)
        if txn is not None:
            matches.append((Path("input") / file_name, txn))

    if not matches:
        raise ValueError(f"No transaction found at source line {line_number}")
    if len(matches) > 1:
        files = [str(item[0]) for item in matches]
        raise ValueError(
            "Source line is ambiguous across files. "
            f"Add --input-file. Matching files: {files}"
        )

    return matches[0]


def _format_pass_fail(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _render_text_report(report: dict) -> str:
    """Render human-readable explain output."""
    lines = []

    txn = report["transaction"]
    lines.append("=" * 72)
    lines.append("Rule Explain Report")
    lines.append("=" * 72)
    lines.append(f"Transaction ID: {txn['transaction_id']}")
    lines.append(f"Input File: {txn['input_file']}")
    lines.append(f"Source Line: {txn['source_line_number']}")
    lines.append(f"Date: {txn['date']}")
    lines.append(f"Amount: {txn['amount']:.2f}")
    lines.append(f"Direction: {txn['transaction_type']}")
    lines.append(f"Service: {txn['service_type'] or '-'}")
    lines.append(f"Provider: {txn['provider'] or '-'}")
    lines.append(f"Notification: {txn['notification_text']}")
    lines.append("")

    pre = report["pre_override"]
    lines.append("Rule match decision")
    lines.append(f"  Winning Rule: {pre['winning_rule'] or '-'}")
    if pre["winning_rule_source"]:
        lines.append(f"  Winning Rule Source: {pre['winning_rule_source']}")
    if pre["winning_rule_layer"] == "overlay":
        if pre["winning_rule_overlay_of"]:
            lines.append(f"  Overlay Of: {pre['winning_rule_overlay_of']}")
        else:
            lines.append("  Overlay Of: - (overlay addition)")
    lines.append(f"  Category: {pre['transaction_category'] or '-'} / {pre['category'] or '-'} / {pre['subcategory'] or '-'}")

    over = report["override"]
    lines.append("")
    lines.append("Transaction override")
    lines.append(f"  Applied: {over['applied']}")
    lines.append(f"  Hidden: {over['hidden']}")
    if over["entry"] is not None:
        lines.append(f"  Entry: {json.dumps(over['entry'], ensure_ascii=False)}")

    final_decision = report["final"]
    lines.append("")
    lines.append("Final decision")
    lines.append(f"  Visible: {not final_decision['hidden']}")
    lines.append(
        f"  Category: {final_decision['transaction_category'] or '-'} / "
        f"{final_decision['category'] or '-'} / {final_decision['subcategory'] or '-'}"
    )

    lines.append("")
    lines.append("Matched rules")
    if report["matched_rules"]:
        for rule in report["matched_rules"]:
            lines.append(
                f"  {rule['key']} [{rule['source']}] (prio {rule['priority']}): "
                f"{rule['transaction_category']} / {rule['category']} / {rule['subcategory']}"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Top non-matching candidate rules")
    if report["non_matching_candidates"]:
        for candidate in report["non_matching_candidates"]:
            failed = candidate["failed_checks"][0] if candidate["failed_checks"] else None
            if failed:
                lines.append(
                    f"  - {candidate['key']} [{candidate['source']}] (prio {candidate['priority']}): "
                    f"first failure {failed['id']} -> {failed['detail']}"
                )
            else:
                lines.append(
                    f"  - {candidate['key']} [{candidate['source']}] (prio {candidate['priority']}): no detailed failure"
                )
    else:
        lines.append("  - none")

    target_rule = report.get("target_rule")
    if target_rule is not None:
        lines.append("")
        lines.append("=" * 72)
        lines.append(f"Target Rule Analysis")
        lines.append("=" * 72)
        lines.append(f"Target Rule: {target_rule['key']}")
        lines.append(f"Target Rule Source: {target_rule['source']}")
        lines.append(f"Target Rule Layer: {target_rule['rule_layer']}")
        if target_rule["rule_layer"] == "overlay":
            lines.append(
                f"Target Overlay Of: {target_rule['overlay_of'] or '- (overlay addition)'}"
            )
        lines.append(f"In candidate scope: {target_rule['in_candidate_scope']}")
        lines.append(f"Matched: {target_rule['matched']}")
        for check in target_rule["checks"]:
            lines.append(
                f"- {_format_pass_fail(check['passed'])} {check['id']}: {check['detail']}"
            )

    return "\n".join(lines)


def build_explain_report(
    run_dir: Path,
    transaction_id: Optional[str],
    line_number: Optional[int],
    input_file: Optional[str],
    rule_id: Optional[str],
    no_overlays: bool,
    no_overrides: bool,
    max_non_matching: int,
) -> dict:
    """Build full explain report for one selected transaction."""
    base_rules_path, overlay_path, overrides_path = _resolve_rules(run_dir)

    effective_overlay_path = None if no_overlays else overlay_path
    overlay_source = Path(effective_overlay_path).as_posix() if effective_overlay_path else None
    engine = RuleEngine(base_rules_path, overlay_path=effective_overlay_path, debug=False)
    index_data = _build_transactions_index(run_dir)
    selected_file, txn = _select_transaction(index_data, transaction_id, line_number, input_file)

    candidate_rules = engine._service_provider_candidates(engine.rules, txn)

    candidate_diagnostics = []
    matched_rules = []
    for rule in candidate_rules:
        explanation = rule.explain_match(txn)
        is_overlay_rule = overlay_source is not None and rule.source == overlay_source
        item = {
            "key": rule.declared_key,
            "name": rule.name,
            "priority": rule.priority,
            "transaction_category": rule.transaction_category,
            "category": rule.category,
            "subcategory": rule.subcategory,
            "source": rule.source,
            "rule_layer": "overlay" if is_overlay_rule else "base",
            "overlay_of": rule.overlay_of,
            "matched": explanation["matched"],
            "checks": explanation["checks"],
            "failed_checks": explanation["failed_checks"],
        }
        candidate_diagnostics.append(item)
        if explanation["matched"]:
            matched_rules.append(item)

    winning_rule = matched_rules[0] if matched_rules else None

    override_entry = None
    override_applied = False
    hidden = False
    final_transaction_category = winning_rule["transaction_category"] if winning_rule else None
    final_category = winning_rule["category"] if winning_rule else None
    final_subcategory = winning_rule["subcategory"] if winning_rule else None

    if not no_overrides:
        transaction_overrides = load_overrides_if_present(overrides_path)
        if transaction_overrides is not None:
            override_entry = transaction_overrides.overrides.get(txn.transaction_id)
            if override_entry is not None:
                override_applied = True
                hidden = bool(override_entry.get("hidden"))
                if "transaction_category" in override_entry:
                    final_transaction_category = override_entry["transaction_category"]
                if "category" in override_entry:
                    final_category = override_entry["category"]
                if "subcategory" in override_entry:
                    final_subcategory = override_entry["subcategory"]

    non_matching_candidates = [
        item for item in candidate_diagnostics if not item["matched"]
    ][:max_non_matching]

    target_rule_report = None
    if rule_id:
        target_rule = next(
            (
                rule for rule in engine.rules
                if rule.key == rule_id or rule.declared_key == rule_id
            ),
            None,
        )
        if target_rule is None:
            raise ValueError(f"Unknown rule ID: {rule_id}")

        target_explanation = target_rule.explain_match(txn)
        candidate_keys = {r.key for r in candidate_rules} | {r.declared_key for r in candidate_rules}
        target_rule_report = {
            "key": target_rule.declared_key,
            "name": target_rule.name,
            "priority": target_rule.priority,
            "source": target_rule.source,
            "rule_layer": "overlay" if (overlay_source is not None and target_rule.source == overlay_source) else "base",
            "overlay_of": target_rule.overlay_of,
            "in_candidate_scope": target_rule.key in candidate_keys or target_rule.declared_key in candidate_keys,
            "matched": target_explanation["matched"],
            "checks": target_explanation["checks"],
            "failed_checks": target_explanation["failed_checks"],
        }

    return {
        "transaction": {
            "transaction_id": txn.transaction_id,
            "input_file": selected_file.as_posix(),
            "source_line_number": txn.source_line_number,
            "date": txn.date.strftime("%Y-%m-%d"),
            "amount": txn.amount,
            "transaction_type": txn.transaction_type,
            "service_type": txn.service_type,
            "provider": txn.provider,
            "notification_text": txn.notification_text,
        },
        "pre_override": {
            "winning_rule": winning_rule["key"] if winning_rule else None,
            "winning_rule_source": winning_rule["source"] if winning_rule else None,
            "winning_rule_layer": winning_rule["rule_layer"] if winning_rule else None,
            "winning_rule_overlay_of": winning_rule["overlay_of"] if winning_rule else None,
            "transaction_category": winning_rule["transaction_category"] if winning_rule else None,
            "category": winning_rule["category"] if winning_rule else None,
            "subcategory": winning_rule["subcategory"] if winning_rule else None,
        },
        "override": {
            "applied": override_applied,
            "hidden": hidden,
            "entry": override_entry,
        },
        "final": {
            "hidden": hidden,
            "transaction_category": final_transaction_category,
            "category": final_category,
            "subcategory": final_subcategory,
        },
        "matched_rules": [
            {
                "key": item["key"],
                "name": item["name"],
                "priority": item["priority"],
                "transaction_category": item["transaction_category"],
                "category": item["category"],
                "subcategory": item["subcategory"],
                "source": item["source"],
                "rule_layer": item["rule_layer"],
                "overlay_of": item["overlay_of"],
            }
            for item in matched_rules
        ],
        "non_matching_candidates": [
            {
                "key": item["key"],
                "name": item["name"],
                "priority": item["priority"],
                "source": item["source"],
                "rule_layer": item["rule_layer"],
                "overlay_of": item["overlay_of"],
                "failed_checks": item["failed_checks"],
            }
            for item in non_matching_candidates
        ],
        "target_rule": target_rule_report,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explain which rules match a single transaction and why. "
            "Select by --transaction-id or by --line-number (with optional --input-file). "
            "Any reported override refers to transaction_overrides.json, not to rule overlay overrides."
        )
    )
    parser.add_argument("run_dir", help="Run directory (e.g. 'example' or 'data/private/dev')")
    parser.add_argument("--transaction-id", help="Transaction ID to inspect (e.g. TX-000123)")
    parser.add_argument("--line-number", type=int, help="1-based source CSV line number")
    parser.add_argument(
        "--input-file",
        "--input",
        dest="input_file",
        help="Input CSV file name (required when line number is ambiguous)",
    )
    parser.add_argument("--rule-id", help="Optional rule key to explain in detail")
    parser.add_argument(
        "--no-overlays",
        action="store_true",
        help="Ignore rule overlays and evaluate only base rules",
    )
    parser.add_argument(
        "--no-overrides",
        action="store_true",
        help="Ignore transaction_overrides.json when computing the final decision",
    )
    parser.add_argument("--max-non-matching", type=int, default=5, help="How many non-matching candidate rules to include")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")

    args = parser.parse_args(argv)

    try:
        run_dir = _resolve_run_directory(args.run_dir)
        report = build_explain_report(
            run_dir=run_dir,
            transaction_id=args.transaction_id,
            line_number=args.line_number,
            input_file=args.input_file,
            rule_id=args.rule_id,
            no_overlays=args.no_overlays,
            no_overrides=args.no_overrides,
            max_non_matching=args.max_non_matching,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ {e}")
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\n")
        print(_render_text_report(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""List what in a dataset needs attention: open reviews, uncategorized rows, dead rules
and overrides that do not do what they seem to.

Read-only: nothing is written to output/ or metadata/. Transaction IDs are assigned in
memory from the persisted registry, exactly as the pipeline would assign them.
"""

import argparse
import contextlib
import io
import json
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from categorize_transactions import _resolve_run_directory
from explain_rule_match import _build_transactions_index
from models import Rule, Transaction
from override_id_remap import normalize_row_text
from rule_engine import RuleEngine, resolve_rule_files
from transaction_overrides import load_overrides_if_present

CATEGORY_FIELDS = ("transaction_category", "category", "subcategory")
ROW_DATE = re.compile(r"^(\d{2}\.\d{2}\.\d{4})")
ROW_WORD = re.compile(r"[^\W\d_]{3,}")


def _amount(txn: Transaction) -> float:
    return round(abs(txn.credit - txn.debit), 2)


def _transaction_item(txn: Transaction) -> dict:
    return {
        "transaction_id": txn.transaction_id,
        "date": txn.date.strftime("%Y-%m-%d") if txn.date else "?",
        "amount": round(txn.amount, 2),
        "text": txn.notification_text,
    }


def _rule_label(rule: Rule) -> dict:
    return {"key": rule.declared_key, "source": rule.source}


def _review_items(transactions, matching_map, overrides) -> list[dict]:
    """Transactions won by a rule with a review question, not yet reviewed or overridden.

    An override counts as a decision, so an overridden transaction is never open.
    """
    items = []
    for idx, txn in enumerate(transactions):
        matching = matching_map.get(idx) or []
        winner = matching[0] if matching else None
        if winner is None or not winner.review or txn.transaction_id in overrides:
            continue
        if winner.reviewed_until and txn.date.date() <= winner.reviewed_until:
            continue
        items.append({
            **_transaction_item(txn),
            "rule": winner.declared_key,
            "question": winner.review,
            "note": winner.note,
        })
    return items


def _rule_findings(own_rules: list[Rule], transactions, matching_map) -> dict:
    """Rules of the dataset itself that never match, never win, or carry unused amounts.

    Base rules are left out: a national baseline naturally has rules a dataset never uses.
    """
    matched_amounts: dict[str, set] = {rule.key: set() for rule in own_rules}
    wins: Counter = Counter()
    beaten_by: dict[str, Counter] = {rule.key: Counter() for rule in own_rules}
    for idx, txn in enumerate(transactions):
        matching = matching_map.get(idx) or []
        if not matching:
            continue
        wins[matching[0].key] += 1
        for rule in matching:
            if rule.key in matched_amounts:
                matched_amounts[rule.key].add(_amount(txn))
                if rule is not matching[0]:
                    beaten_by[rule.key][matching[0].declared_key] += 1

    never_matching, never_winning, unused_amounts = [], [], []
    for rule in own_rules:
        if not matched_amounts[rule.key]:
            never_matching.append(_rule_label(rule))
        elif wins[rule.key] == 0:
            never_winning.append({
                **_rule_label(rule),
                "beaten_by": dict(beaten_by[rule.key].most_common()),
            })
        unused = [a for a in rule.amounts if round(a, 2) not in matched_amounts[rule.key]]
        # A rule that never matches is already reported; its amounts add nothing.
        if unused and matched_amounts[rule.key]:
            unused_amounts.append({**_rule_label(rule), "amounts": unused})
    return {
        "never_matching": never_matching,
        "never_winning": never_winning,
        "unused_amounts": unused_amounts,
    }


def _row_problem(row_hint: str, txn: Transaction) -> Optional[str]:
    """Why a `_row` hint does not describe *txn*, or None if it does.

    Hints are often abbreviated by hand ("30.03.2025;Karteneinkauf BYRO BASEL"), so they
    are not compared as a whole: the leading date must be the transaction's, and at least
    half of the hint's words must occur in the source row.
    """
    hint = normalize_row_text(row_hint)
    date_match = ROW_DATE.match(hint)
    if date_match and txn.date and date_match.group(1) != txn.date.strftime("%d.%m.%Y"):
        return f"date {date_match.group(1)} differs"
    words = set(ROW_WORD.findall(hint))
    row = normalize_row_text(txn.source_row_text)
    missing = sorted(w for w in words if w not in row)
    if words and len(missing) * 2 > len(words):
        return f"words not in row: {', '.join(missing)}"
    return None


def _override_findings(overrides: dict, transactions: list[Transaction]) -> dict:
    """Overrides that cannot apply, may apply to the wrong row, or change nothing.

    *transactions* carry the rule result before overrides.
    """
    by_id = {txn.transaction_id: txn for txn in transactions}
    unknown, row_mismatch, without_effect, without_row = [], [], [], []
    for tx_id, entry in overrides.items():
        txn = by_id.get(tx_id)
        if txn is None:
            unknown.append({"transaction_id": tx_id, "row": entry.get("_row", "")})
            continue

        row_hint = entry.get("_row")
        if not row_hint:
            without_row.append(_transaction_item(txn))
        else:
            problem = _row_problem(row_hint, txn)
            if problem:
                row_mismatch.append({**_transaction_item(txn), "row": row_hint, "problem": problem})

        if entry.get("hidden") or "split" in entry:
            continue
        current = {
            "transaction_category": txn.auto_transaction_category,
            "category": txn.auto_category,
            "subcategory": txn.auto_subcategory,
        }
        if all(entry[f] == current[f] for f in CATEGORY_FIELDS if f in entry):
            without_effect.append(_transaction_item(txn))

    return {
        "unknown_ids": unknown,
        "row_mismatch": row_mismatch,
        "without_effect": without_effect,
        "without_row": without_row,
    }


def build_doctor_report(run_dir: Path) -> dict:
    """Categorize the dataset in memory and collect everything that needs attention."""
    _, base_rule_files, overlay_rule_files = resolve_rule_files(run_dir)
    own_sources = {p.as_posix() for p in (overlay_rule_files or base_rule_files)}

    # Engine and import report their loading steps on stdout, which would drown the findings.
    with contextlib.redirect_stdout(io.StringIO()):
        engine = RuleEngine(base_rule_files, overlay_path=overlay_rule_files)
        index = _build_transactions_index(run_dir)
    transactions = [txn for _, txn in index["all_transactions"]]
    transactions, matching_map = engine.categorize_batch(transactions)

    overrides_file = load_overrides_if_present(str(run_dir / "transaction_overrides.json"))
    overrides = overrides_file.overrides if overrides_file else {}

    final = [replace(txn) for txn in transactions]
    if overrides_file:
        final = overrides_file.apply(final)
    uncategorized = [_transaction_item(t) for t in final if not t.auto_category]

    own_rules = [rule for rule in engine.rules if rule.source in own_sources]
    return {
        "run_dir": run_dir.as_posix(),
        "transactions": len(transactions),
        "rules": len(engine.rules),
        "own_rules": len(own_rules),
        "overrides": len(overrides),
        "to_review": _review_items(transactions, matching_map, overrides),
        "uncategorized": uncategorized,
        "rules_findings": _rule_findings(own_rules, transactions, matching_map),
        "override_findings": _override_findings(overrides, transactions),
    }


def count_findings(report: dict) -> int:
    return (
        len(report["to_review"])
        + len(report["uncategorized"])
        + sum(len(v) for v in report["rules_findings"].values())
        + sum(len(v) for v in report["override_findings"].values())
    )


def _format_transaction(item: dict) -> str:
    return f"{item['transaction_id']}  {item['date']}  {item['amount']:>10.2f}  {item['text'][:90]}"


def _render_text_report(report: dict) -> str:
    lines = [
        f"Doctor: {report['run_dir']}",
        f"  {report['transactions']} transactions, {report['rules']} rules "
        f"({report['own_rules']} from this dataset), {report['overrides']} overrides",
    ]

    def section(title: str, items: list, render, count: Optional[int] = None) -> None:
        if not items:
            return
        lines.append("")
        lines.append(f"{title} ({len(items) if count is None else count})")
        for item in items:
            lines.extend(f"  {line}" for line in render(item))

    # Grouped by rule, so that question and note are printed once per rule.
    by_rule: dict[str, list] = {}
    for item in report["to_review"]:
        by_rule.setdefault(item["rule"], []).append(item)
    section(
        "To review",
        [{"rule": rule, "items": items} for rule, items in by_rule.items()],
        lambda g: [
            f"{g['rule']}  ({len(g['items'])})",
            f"  ? {g['items'][0]['question']}",
        ]
        + ([f"  note: {g['items'][0]['note']}"] if g["items"][0]["note"] else [])
        + [f"  {_format_transaction(i)}" for i in g["items"]],
        count=len(report["to_review"]),
    )
    section("Uncategorized", report["uncategorized"], lambda i: [_format_transaction(i)])

    rules = report["rules_findings"]
    section("Rules that never match", rules["never_matching"], lambda i: [f"{i['key']}  ({i['source']})"])
    section(
        "Rules that match but never win",
        rules["never_winning"],
        lambda i: [
            f"{i['key']}  ({i['source']})  beaten by: "
            + ", ".join(f"{k} ({n}x)" for k, n in i["beaten_by"].items())
        ],
    )
    section(
        "Amounts that never match",
        rules["unused_amounts"],
        lambda i: [f"{i['key']}: {', '.join(f'{a:.2f}' for a in i['amounts'])}  ({i['source']})"],
    )

    overrides = report["override_findings"]
    section(
        "Overrides with unknown IDs (see suggest_override_ids.py)",
        overrides["unknown_ids"],
        lambda i: [f"{i['transaction_id']}  _row: {i['row'] or '-'}"],
    )
    section(
        "Overrides whose _row does not fit their transaction (IDs shifted?)",
        overrides["row_mismatch"],
        lambda i: [
            _format_transaction(i),
            f"    _row: {i['row']}",
            f"    {i['problem']}",
        ],
    )
    section(
        "Overrides that change nothing",
        overrides["without_effect"],
        lambda i: [_format_transaction(i)],
    )
    section("Overrides without _row", overrides["without_row"], lambda i: [_format_transaction(i)])

    total = count_findings(report)
    lines.append("")
    lines.append("No findings." if total == 0 else f"{total} finding(s).")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "List what in a dataset needs attention: transactions to review, uncategorized "
            "transactions, rules that never match or never win, and suspicious overrides. "
            "Writes nothing. Exits with 1 when there are findings."
        )
    )
    parser.add_argument("run_dir", help="Run directory (e.g. 'example' or 'data/private/2026')")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args(argv)

    try:
        run_dir = _resolve_run_directory(args.run_dir)
        report = build_doctor_report(run_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ {e}")
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_text_report(report))
    return 1 if count_findings(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())

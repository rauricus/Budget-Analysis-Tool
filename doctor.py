#!/usr/bin/env python3
"""List what in a dataset needs attention: open reviews, uncategorized rows, dead rules
and overrides that do not do what they seem to.

Read-only: nothing is written to output/ or metadata/. Transaction IDs are assigned in
memory from the persisted registry, exactly as the pipeline would assign them.
"""

import argparse
import calendar
import contextlib
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from dataclasses import replace
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from categorize_transactions import _resolve_run_directory
from explain_rule_match import _build_transactions_index
from models import Rule, Transaction
from override_id_remap import normalize_row_text
from rule_engine import RuleEngine, apply_rule_splits, resolve_rule_files
from transaction_overrides import load_overrides_if_present

CATEGORY_FIELDS = ("transaction_category", "category", "subcategory")
EXPORT_CATEGORY_COLUMNS = ("Transaction Category", "Category", "Subcategory")
ROW_DATE = re.compile(r"^(\d{2}\.\d{2}\.\d{4})")
ROW_WORD = re.compile(r"[^\W\d_]{3,}")
YEAR_IN_NAME = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


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


def _outcome(rule: Rule) -> tuple:
    return (rule.transaction_category, rule.category, rule.subcategory)


def _period_reason(rule: Rule, first: date, last: date, years: set) -> str:
    """Why a rule that never matches may belong to another period, or "" if nothing hints so.

    A year in key or name is only a hint, so it is only reported for rules that never match.
    """
    if rule.valid_to and rule.valid_to < first:
        return f"valid_to {rule.valid_to} is before the first transaction ({first})"
    if rule.valid_from and rule.valid_from > last:
        return f"valid_from {rule.valid_from} is after the last transaction ({last})"
    named = set(YEAR_IN_NAME.findall(f"{rule.declared_key} {rule.name}"))
    if named and not any(int(year) in years for year in named):
        covered = ", ".join(str(year) for year in sorted(years))
        return f"names {', '.join(sorted(named))}, the data covers {covered}"
    return ""


def _rule_findings(own_rules: list[Rule], transactions, matching_map) -> dict:
    """Rules of the dataset itself that never match, never win, or carry unused amounts,
    plus review dates beyond the data and equal-priority ties across all rules.

    Base rules are left out of the first three: a national baseline naturally has rules a
    dataset never uses. Ties are reported for any rule, since they decide a result.
    """
    dates = [txn.date.date() for txn in transactions if txn.date]
    first, last = min(dates, default=None), max(dates, default=None)
    years = {d.year for d in dates}

    matched_amounts: dict[str, set] = {rule.key: set() for rule in own_rules}
    wins: Counter = Counter()
    beaten_by: dict[str, Counter] = {rule.key: Counter() for rule in own_rules}
    ties: Counter = Counter()
    for idx, txn in enumerate(transactions):
        matching = matching_map.get(idx) or []
        if not matching:
            continue
        wins[matching[0].key] += 1
        # Equal priority leaves the result to load order (see AGENTS.md, "Traps").
        if (
            len(matching) > 1
            and matching[0].priority == matching[1].priority
            and _outcome(matching[0]) != _outcome(matching[1])
        ):
            ties[(matching[0].declared_key, matching[1].declared_key, matching[0].priority)] += 1
        for rule in matching:
            if rule.key in matched_amounts:
                matched_amounts[rule.key].add(_amount(txn))
                if rule is not matching[0]:
                    beaten_by[rule.key][matching[0].declared_key] += 1

    never_matching, never_winning, unused_amounts = [], [], []
    for rule in own_rules:
        if not matched_amounts[rule.key]:
            reason = _period_reason(rule, first, last, years) if first else ""
            never_matching.append({**_rule_label(rule), "reason": reason})
        elif wins[rule.key] == 0:
            never_winning.append({
                **_rule_label(rule),
                "beaten_by": dict(beaten_by[rule.key].most_common()),
            })
        unused = [a for a in rule.amounts if round(a, 2) not in matched_amounts[rule.key]]
        # A rule that never matches is already reported; its amounts add nothing.
        if unused and matched_amounts[rule.key]:
            unused_amounts.append({**_rule_label(rule), "amounts": unused})

    # Transactions imported later but dated up to reviewed_until would count as reviewed
    # without ever having been seen. Exports cover whole months, so reviewing up to the end
    # of the last month is fine even if its last booking is earlier.
    month_end = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1]) if last else None
    review_after_data = [
        {**_rule_label(rule), "reviewed_until": rule.reviewed_until.isoformat(), "month_end": month_end.isoformat()}
        for rule in own_rules
        if rule.reviewed_until and month_end and rule.reviewed_until > month_end
    ]
    priority_ties = [
        {"winner": winner, "loser": loser, "priority": priority, "transactions": count}
        for (winner, loser, priority), count in sorted(ties.items())
    ]
    return {
        "never_matching": never_matching,
        "never_winning": never_winning,
        "unused_amounts": unused_amounts,
        "review_after_data": review_after_data,
        "priority_ties": priority_ties,
    }


def _input_months(transactions: list[Transaction]) -> list[str]:
    """Months with at least one transaction, as 'YYYY-MM' like metadata/months.json."""
    return sorted({txn.date.strftime("%Y-%m") for txn in transactions if txn.date})


def _input_findings(all_transactions: list, input_months: list[str]) -> dict:
    """Input files that overlap, and calendar months without any transaction.

    IDs are assigned per file with a per-file occurrence counter, so the same booking in two
    files gets the same ID in both — and is exported, and counted, twice.
    """
    files_by_id: dict[str, set] = defaultdict(set)
    for path, txn in all_transactions:
        files_by_id[txn.transaction_id].add(path.name)
    overlaps = Counter(tuple(sorted(files)) for files in files_by_id.values() if len(files) > 1)

    missing_months = []
    if input_months:
        year, month = map(int, input_months[0].split("-"))
        while f"{year}-{month:02d}" < input_months[-1]:
            if f"{year}-{month:02d}" not in input_months:
                missing_months.append(f"{year}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return {
        "overlapping_files": [
            {"files": list(files), "transactions": count} for files, count in sorted(overlaps.items())
        ],
        "missing_months": missing_months,
    }


def _output_findings(run_dir: Path, final: list[Transaction], input_months: list[str]) -> dict:
    """Differences between what the pipeline last wrote and the current input and rules.

    budget_report.py and the Excel report read the categorized CSVs, not the rules, and
    take their months from metadata/months.json. After a rule or override change without a
    pipeline run, or after a run with --input-file (which rewrites months.json with that
    file's months only), they silently work on an old or partial state.
    Uncategorized rows are skipped: --use-input-category-fallback fills them on export.
    """
    months_path = run_dir / "metadata" / "months.json"
    recorded_months = []
    if months_path.exists():
        with open(months_path, "r", encoding="utf-8") as f:
            recorded_months = json.load(f)

    exported: dict[str, tuple] = {}
    for path in sorted((run_dir / "output").glob("*.categorized.csv")):
        with open(path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                exported[row["Transaction ID"]] = tuple(row.get(c) or "" for c in EXPORT_CATEGORY_COLUMNS)

    current = {txn.transaction_id: txn for txn in final}
    differs = []
    for tx_id, txn in current.items():
        if tx_id not in exported or not txn.auto_category:
            continue
        expected = (
            txn.auto_transaction_category or "",
            txn.auto_category or "",
            txn.auto_subcategory or "",
        )
        if exported[tx_id] != expected:
            differs.append({
                **_transaction_item(txn),
                "exported": " / ".join(exported[tx_id]),
                "current": " / ".join(expected),
            })
    return {
        "differs": differs,
        "missing_in_output": [_transaction_item(txn) for tx_id, txn in current.items() if tx_id not in exported],
        "extra_in_output": sorted(set(exported) - set(current)),
        "months_not_recorded": [m for m in input_months if m not in recorded_months],
        "recorded_months_without_input": [m for m in recorded_months if m not in input_months],
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
    all_transactions = index["all_transactions"]
    transactions = [txn for _, txn in all_transactions]
    transactions, matching_map = engine.categorize_batch(transactions)

    overrides_file = load_overrides_if_present(str(run_dir / "transaction_overrides.json"))
    overrides = overrides_file.overrides if overrides_file else {}

    final = [replace(txn) for txn in transactions]
    if overrides_file:
        final = overrides_file.apply(final)
    winners = {
        txn.transaction_id: (matching_map.get(idx) or [None])[0] for idx, txn in enumerate(transactions)
    }
    final = apply_rule_splits(final, winners, overrides)
    uncategorized = [_transaction_item(t) for t in final if not t.auto_category]

    own_rules = [rule for rule in engine.rules if rule.source in own_sources]
    input_months = _input_months(transactions)
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
        "input_findings": _input_findings(all_transactions, input_months),
        "output_findings": _output_findings(run_dir, final, input_months),
    }


def count_findings(report: dict) -> int:
    return (
        len(report["to_review"])
        + len(report["uncategorized"])
        + sum(len(v) for v in report["rules_findings"].values())
        + sum(len(v) for v in report["override_findings"].values())
        + sum(len(v) for v in report["input_findings"].values())
        + sum(len(v) for v in report["output_findings"].values())
    )


def _format_transaction(item: dict) -> str:
    return f"{item['transaction_id']}  {item['date']}  {item['amount']:>10.2f}  {item['text'][:90]}"


def _render_text_report(report: dict) -> str:
    lines = [
        f"Doctor: {report['run_dir']}",
        f"  {report['transactions']} transactions, {report['rules']} rules "
        f"({report['own_rules']} from this dataset), {report['overrides']} overrides",
    ]

    def section(title: str, items: list, render, count: Optional[int] = None, limit: Optional[int] = None) -> None:
        if not items:
            return
        lines.append("")
        lines.append(f"{title} ({len(items) if count is None else count})")
        for item in items[:limit]:
            lines.extend(f"  {line}" for line in render(item))
        if limit is not None and len(items) > limit:
            lines.append(f"  ... and {len(items) - limit} more")

    # Grouped by rule, so that question and note are printed once per rule.
    by_rule: dict[str, list] = {}
    for item in report["to_review"]:
        by_rule.setdefault(item["rule"], []).append(item)
    inputs = report["input_findings"]
    section(
        "Input files that overlap (their shared transactions are counted twice)",
        inputs["overlapping_files"],
        lambda i: [f"{' + '.join(i['files'])}: {i['transactions']} transaction(s)"],
    )
    section("Months without any transaction", inputs["missing_months"], lambda m: [m])

    outputs = report["output_findings"]
    stale = "rerun categorize_transactions.py before the reports"
    section(
        f"Output rows that differ from the current rules ({stale})",
        outputs["differs"],
        lambda i: [f"{_format_transaction(i)}", f"    output: {i['exported']}  now: {i['current']}"],
        limit=10,
    )
    section(
        f"Transactions missing from output/ ({stale})",
        outputs["missing_in_output"],
        lambda i: [_format_transaction(i)],
        limit=10,
    )
    section(
        f"Output rows without a transaction ({stale})",
        outputs["extra_in_output"],
        lambda tx_id: [tx_id],
        limit=10,
    )
    section(f"Input months missing from metadata/months.json ({stale})", outputs["months_not_recorded"], lambda m: [m])
    section(
        f"Months in metadata/months.json without input ({stale})",
        outputs["recorded_months_without_input"],
        lambda m: [m],
    )

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
    section(
        "Rules that never match",
        rules["never_matching"],
        lambda i: [f"{i['key']}  ({i['source']})" + (f"  -- {i['reason']}" if i["reason"] else "")],
    )
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
    section(
        "Review dates after the last transaction (later imports would count as reviewed)",
        rules["review_after_data"],
        lambda i: [f"{i['key']}: reviewed_until {i['reviewed_until']}, data ends {i['month_end']}  ({i['source']})"],
    )
    section(
        "Equal-priority rules with different results (load order decides)",
        rules["priority_ties"],
        lambda i: [f"{i['winner']} over {i['loser']} at priority {i['priority']}: {i['transactions']} transaction(s)"],
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
            "List what in a dataset needs attention: overlapping or missing input, stale "
            "output, transactions to review, uncategorized transactions, rules that never "
            "match, never win or tie, and suspicious overrides. "
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

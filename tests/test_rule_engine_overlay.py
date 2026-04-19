#!/usr/bin/env python3
"""Tests for RuleEngine base rules, overlay merging, and debug output."""
import json
import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Transaction
from rule_engine import RuleEngine


def _rule(id, category="Kategorie A", subcategory="", priority=50, merchant="TESTLADEN", name=None):
    return {
        "id": id,
        "name": name or f"Regel {id}",
        "transaction_category": "expense",
        "category": category,
        "subcategory": subcategory,
        "scope": {
            "transaction_type": "Debit",
            "transaction_type_detail": None,
            "services": ["Card Purchase"],
            "providers": ["Apple Pay"],
            "notification_filters": {
                "merchants": [merchant],
                "locations": [],
                "include_keywords": [],
                "exclude_keywords": [],
            },
        },
        "priority": priority,
    }


def _write(path, rules):
    path.write_text(json.dumps({"rules": rules}), encoding="utf-8")


class TestBaseRulesOnly:
    def test_loads_all_base_rules(self, tmp_path):
        base = tmp_path / "rules.json"
        _write(base, [_rule(1), _rule(2), _rule(3)])

        engine = RuleEngine(str(base))

        assert len(engine.rules) == 3
        assert {r.id for r in engine.rules} == {1, 2, 3}

    def test_rules_sorted_by_priority_descending(self, tmp_path):
        base = tmp_path / "rules.json"
        _write(base, [_rule(1, priority=10), _rule(2, priority=90), _rule(3, priority=50)])

        engine = RuleEngine(str(base))

        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_missing_base_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RuleEngine(str(tmp_path / "nonexistent.json"))


class TestOverlay:
    def test_loads_optional_transaction_type_detail(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule(1), "scope": {**_rule(1)["scope"], "transaction_type_detail": "Send Money"}}])

        engine = RuleEngine(str(base))

        rule = next(r for r in engine.rules if r.id == 1)
        assert rule.transaction_type_detail == "Send Money"

    def test_null_transaction_type_detail_is_supported(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule(1), "scope": {**_rule(1)["scope"], "transaction_type_detail": None}}])

        engine = RuleEngine(str(base))

        rule = next(r for r in engine.rules if r.id == 1)
        assert rule.transaction_type_detail is None

    def test_overlay_adds_new_rule(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1), _rule(2)])
        _write(overlay, [_rule(99)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        assert len(engine.rules) == 3
        assert 99 in {r.id for r in engine.rules}

    def test_overlay_overrides_existing_rule(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, category="Alt")])
        _write(overlay, [_rule(1, category="Neu")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        rule = next(r for r in engine.rules if r.id == 1)
        assert rule.category == "Neu"
        assert len(engine.rules) == 1  # keine Duplikate

    def test_overlay_override_does_not_duplicate(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1), _rule(2)])
        _write(overlay, [_rule(1, category="Übersteuert"), _rule(3)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        assert len(engine.rules) == 3  # 1 (overridden) + 2 (base) + 3 (new)

    def test_source_attribute_set_from_base(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule(1)])

        engine = RuleEngine(str(base))

        assert engine.rules[0].source == str(base)

    def test_source_attribute_set_from_overlay(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1)])
        _write(overlay, [_rule(2)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        by_id = {r.id: r for r in engine.rules}
        assert by_id[1].source == str(base)
        assert by_id[2].source == str(overlay)

    def test_source_updated_on_override(self, tmp_path):
        """When an overlay overrides a base rule, source reflects the overlay file."""
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, category="Alt")])
        _write(overlay, [_rule(1, category="Neu")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        rule = next(r for r in engine.rules if r.id == 1)
        assert rule.source == str(overlay)

    def test_debug_output_lists_overridden_rules(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, category="Alt")])
        _write(overlay, [_rule(1, name="Neu", category="Neu")])

        RuleEngine(str(base), overlay_path=str(overlay), debug=True)

        captured = capsys.readouterr()
        assert f"Applied overlay {overlay}: 1 overridden, 0 added" in captured.out
        assert f"Override #1: 'Regel 1' from {base} -> 'Neu' from {overlay}" in captured.out

    def test_debug_output_lists_matched_rule_and_source(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        _write(base, [_rule(1, category="Kategorie Test", merchant="MATCHSHOP")])
        engine = RuleEngine(str(base), debug=True)

        transaction = Transaction(
            date=datetime(2025, 3, 21),
            notification_text="Apple Pay MATCHSHOP Aarau",
            credit=0.0,
            debit=12.5,
            label="",
            category="",
            service_type="Card Purchase",
            provider="Apple Pay",
            parsed_merchant="MATCHSHOP",
            parsed_location="Aarau",
        )

        engine.categorize_batch([transaction])

        captured = capsys.readouterr()
        assert "Rule matched: #1 'Regel 1'" in captured.out
        assert f"from {base}" in captured.out
        assert "-> Kategorie Test" in captured.out

    def test_debug_output_suppressed_without_debug_flag(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, category="Alt", merchant="MATCHSHOP")])
        _write(overlay, [_rule(1, name="Neu", category="Neu", merchant="MATCHSHOP")])

        engine = RuleEngine(str(base), overlay_path=str(overlay), debug=False)

        transaction = Transaction(
            date=datetime(2025, 3, 21),
            notification_text="Apple Pay MATCHSHOP Aarau",
            credit=0.0,
            debit=12.5,
            label="",
            category="",
            service_type="Card Purchase",
            provider="Apple Pay",
            parsed_merchant="MATCHSHOP",
            parsed_location="Aarau",
        )

        capsys.readouterr()
        engine.categorize_batch([transaction])

        captured = capsys.readouterr()
        assert "Override #1:" not in captured.out
        assert "Rule matched:" not in captured.out

    def test_overlay_missing_is_silently_skipped(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule(1)])

        engine = RuleEngine(str(base), overlay_path=str(tmp_path / "nonexistent.json"))

        assert len(engine.rules) == 1

    def test_no_overlay_path_loads_only_base(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule(1), _rule(2)])

        engine = RuleEngine(str(base))

        assert len(engine.rules) == 2

    def test_priority_sorting_preserved_after_overlay(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, priority=10), _rule(2, priority=50)])
        _write(overlay, [_rule(3, priority=30)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_invalid_transaction_category_raises(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule(1), "transaction_category": "invalid"}])

        with pytest.raises(ValueError):
            RuleEngine(str(base))

    def test_sets_auto_transaction_category_on_match(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule(1, category="Kategorie Test")])
        engine = RuleEngine(str(base))

        transaction = Transaction(
            date=datetime(2025, 3, 21),
            notification_text="Apple Pay TESTLADEN Aarau",
            credit=0.0,
            debit=9.5,
            label="",
            category="",
            service_type="Card Purchase",
            provider="Apple Pay",
            parsed_merchant="TESTLADEN",
            parsed_location="Aarau",
        )

        categorized, _ = engine.categorize_batch([transaction])
        assert categorized[0].auto_transaction_category == "Expense"

#!/usr/bin/env python3
"""Tests for RuleEngine base rules, overlay merging, and debug output."""
import json
import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Transaction
from rule_engine import RuleEngine, discover_rule_files, resolve_rule_files


def _rule(key, category="Kategorie A", subcategory="", priority=5, merchant="TESTLADEN", name=None, overlay_of=None):
    r = {
        "key": key,
        "name": name or f"Regel {key}",
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
    if overlay_of is not None:
        r["overlay_of"] = overlay_of
    return r


def _write(path, rules):
    path.write_text(json.dumps({"rules": rules}), encoding="utf-8")


class TestBaseRulesOnly:
    def test_loads_all_base_rules(self, tmp_path):
        base = tmp_path / "rules.json"
        _write(base, [_rule("rule_1"), _rule("rule_2"), _rule("rule_3")])

        engine = RuleEngine(str(base))

        assert len(engine.rules) == 3
        assert {r.key for r in engine.rules} == {"rule_1", "rule_2", "rule_3"}

    def test_rules_sorted_by_priority_descending(self, tmp_path):
        base = tmp_path / "rules.json"
        _write(base, [_rule("rule_1", priority=1), _rule("rule_2", priority=10), _rule("rule_3", priority=5)])

        engine = RuleEngine(str(base))

        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_missing_base_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RuleEngine(str(tmp_path / "nonexistent.json"))


class TestOverlay:
    def test_loads_optional_transaction_type_detail(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule("rule_1"), "scope": {**_rule("rule_1")["scope"], "transaction_type_detail": "Send Money"}}])

        engine = RuleEngine(str(base))

        rule = next(r for r in engine.rules if r.key == "rule_1")
        assert rule.transaction_type_detail == "Send Money"

    def test_loads_counterparty_filters(self, tmp_path):
        base = tmp_path / "base.json"
        _write(
            base,
            [{
                **_rule("rule_1"),
                "scope": {
                    **_rule("rule_1")["scope"],
                    "notification_filters": {
                        **_rule("rule_1")["scope"]["notification_filters"],
                        "counterparties": ["DOCUTEAM AG"],
                        "counterparty_ibans": ["CH6709000000400025000"],
                    },
                },
            }],
        )

        engine = RuleEngine(str(base))

        rule = next(r for r in engine.rules if r.key == "rule_1")
        assert rule.counterparties == ["DOCUTEAM AG"]
        assert rule.counterparty_ibans == ["CH6709000000400025000"]

    def test_null_transaction_type_detail_is_supported(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule("rule_1"), "scope": {**_rule("rule_1")["scope"], "transaction_type_detail": None}}])

        engine = RuleEngine(str(base))

        rule = next(r for r in engine.rules if r.key == "rule_1")
        assert rule.transaction_type_detail is None

    def test_overlay_adds_new_rule(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1"), _rule("rule_2")])
        _write(overlay, [_rule("rule_99")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        assert len(engine.rules) == 3
        assert "rule_99" in {r.key for r in engine.rules}

    def test_overlay_overrides_existing_rule(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1", category="Alt")])
        _write(overlay, [_rule("rule_1_overlay", category="Neu", overlay_of="rule_1")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        rule = next(r for r in engine.rules if r.key == "rule_1")
        assert rule.category == "Neu"
        assert len(engine.rules) == 1  # keine Duplikate

    def test_overlay_override_does_not_duplicate(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1"), _rule("rule_2")])
        _write(overlay, [_rule("rule_1_overlay", category="Übersteuert", overlay_of="rule_1"), _rule("rule_3")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        assert len(engine.rules) == 3  # rule_1 (replaced via overlay) + rule_2 (base) + rule_3 (new)

    def test_source_attribute_set_from_base(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1")])

        engine = RuleEngine(str(base))

        assert engine.rules[0].source == str(base)

    def test_source_attribute_set_from_overlay(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1")])
        _write(overlay, [_rule("rule_2")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        by_key = {r.key: r for r in engine.rules}
        assert by_key["rule_1"].source == str(base)
        assert by_key["rule_2"].source == str(overlay)

    def test_source_updated_on_override(self, tmp_path):
        """When an overlay overrides a base rule, source reflects the overlay file."""
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1", category="Alt")])
        _write(overlay, [_rule("rule_1_overlay", category="Neu", overlay_of="rule_1")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        rule = next(r for r in engine.rules if r.key == "rule_1")
        assert rule.source == str(overlay)

    def test_debug_output_lists_overlay_replacements(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1", category="Alt")])
        _write(overlay, [_rule("rule_1_overlay", name="Neu", category="Neu", overlay_of="rule_1")])

        RuleEngine(str(base), overlay_path=str(overlay), debug=True)

        captured = capsys.readouterr()
        assert "Applied overlay (1 file(s)): 1 replaced, 0 added" in captured.out
        assert f"Overlay replacement 'rule_1': 'Regel rule_1' from {base} -> 'Neu' from {overlay}" in captured.out

    def test_categorize_batch_emits_no_per_row_debug_output(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1", category="Kategorie Test", merchant="MATCHSHOP")])
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
        assert "Rule matched:" not in captured.out
        assert "No matching rule" not in captured.out

    def test_debug_output_suppressed_without_debug_flag(self, tmp_path, capsys):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1", category="Alt", merchant="MATCHSHOP")])
        _write(overlay, [_rule("rule_1_overlay", name="Neu", category="Neu", merchant="MATCHSHOP", overlay_of="rule_1")])

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
        assert "Overlay replacement 'rule_1':" not in captured.out
        assert "Rule matched:" not in captured.out

    def test_overlay_missing_is_silently_skipped(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1")])

        engine = RuleEngine(str(base), overlay_path=str(tmp_path / "nonexistent.json"))

        assert len(engine.rules) == 1

    def test_no_overlay_path_loads_only_base(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1"), _rule("rule_2")])

        engine = RuleEngine(str(base))

        assert len(engine.rules) == 2

    def test_priority_sorting_preserved_after_overlay(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1", priority=1), _rule("rule_2", priority=5)])
        _write(overlay, [_rule("rule_3", priority=3)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_invalid_priority_raises(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule("rule_1"), "priority": 11}])

        with pytest.raises(ValueError):
            RuleEngine(str(base))

    def test_invalid_transaction_category_raises(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [{**_rule("rule_1"), "transaction_category": "invalid"}])

        with pytest.raises(ValueError):
            RuleEngine(str(base))

    def test_duplicate_key_in_same_file_raises(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1"), _rule("rule_1", category="Duplikat")])

        with pytest.raises(ValueError, match="Duplicate key 'rule_1'"):
            RuleEngine(str(base))

    def test_overlay_key_collision_without_overlay_field_raises(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1")])
        _write(overlay, [_rule("rule_1", category="Kollision")])

        with pytest.raises(ValueError, match="overlay_of"):
            RuleEngine(str(base), overlay_path=str(overlay))

    def test_overlay_unknown_key_raises(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule("rule_1")])
        _write(overlay, [_rule("rule_99_overlay", overlay_of="rule_99")])

        with pytest.raises(ValueError, match="rule_99"):
            RuleEngine(str(base), overlay_path=str(overlay))

    def test_sets_auto_transaction_category_on_match(self, tmp_path):
        base = tmp_path / "base.json"
        _write(base, [_rule("rule_1", category="Kategorie Test")])
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


def _write_data(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


class TestSplitRuleFiles:
    def test_discover_lists_main_file_first_then_parts_by_name(self, tmp_path):
        _write(tmp_path / "rules.json", [])
        _write(tmp_path / "rules.zeta.json", [])
        _write(tmp_path / "rules.alpha.json", [])
        _write(tmp_path / "other.json", [])

        files = discover_rule_files(tmp_path)

        assert [f.name for f in files] == ["rules.json", "rules.alpha.json", "rules.zeta.json"]

    def test_discover_requires_main_file(self, tmp_path):
        _write(tmp_path / "rules.alpha.json", [])

        with pytest.raises(FileNotFoundError):
            discover_rule_files(tmp_path)

    def test_parts_are_merged_into_one_layer_with_their_own_source(self, tmp_path):
        _write(tmp_path / "rules.json", [_rule("rule_1")])
        _write(tmp_path / "rules.ferien.json", [_rule("rule_2")])

        engine = RuleEngine(discover_rule_files(tmp_path))

        sources = {r.key: r.source for r in engine.rules}
        assert sources == {
            "rule_1": (tmp_path / "rules.json").as_posix(),
            "rule_2": (tmp_path / "rules.ferien.json").as_posix(),
        }

    def test_duplicate_key_across_parts_raises(self, tmp_path):
        _write(tmp_path / "rules.json", [_rule("rule_1")])
        _write(tmp_path / "rules.ferien.json", [_rule("rule_1", category="Duplikat")])

        with pytest.raises(ValueError, match="Duplicate key 'rule_1'.*rules.ferien.json"):
            RuleEngine(discover_rule_files(tmp_path))

    def test_base_field_in_part_raises(self, tmp_path):
        _write(tmp_path / "rules.json", [])
        _write_data(tmp_path / "rules.ferien.json", {"base": "reference", "rules": []})

        with pytest.raises(ValueError, match="'base' is only allowed in rules.json"):
            RuleEngine(discover_rule_files(tmp_path))

    def test_overlay_part_replaces_rule_from_base_part(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "data" / "mybase"
        base_dir.mkdir(parents=True)
        _write(base_dir / "rules.json", [_rule("rule_1")])
        _write(base_dir / "rules.ferien.json", [_rule("rule_2", category="Alt")])
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_data(run_dir / "rules.json", {"base": "mybase", "rules": []})
        _write(run_dir / "rules.ferien.json", [_rule("rule_2_overlay", category="Neu", overlay_of="rule_2")])
        monkeypatch.chdir(tmp_path)

        base_name, base_files, overlay_files = resolve_rule_files(run_dir)
        engine = RuleEngine(base_files, overlay_path=overlay_files)

        assert base_name == "mybase"
        rule = next(r for r in engine.rules if r.key == "rule_2")
        assert rule.category == "Neu"
        assert rule.declared_key == "rule_2_overlay"
        assert rule.source == (run_dir / "rules.ferien.json").as_posix()

    def test_resolve_standalone_dataset_has_no_overlay(self, tmp_path):
        _write(tmp_path / "rules.json", [_rule("rule_1")])
        _write(tmp_path / "rules.ferien.json", [_rule("rule_2")])

        base_name, base_files, overlay_files = resolve_rule_files(tmp_path)

        assert base_name is None
        assert [f.name for f in base_files] == ["rules.json", "rules.ferien.json"]
        assert overlay_files == []

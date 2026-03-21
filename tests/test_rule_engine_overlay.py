#!/usr/bin/env python3
"""Tests for RuleEngine base rules and overlay merging."""
import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rule_engine import RuleEngine


def _rule(id, category="Kategorie A", priority=50, merchant="TESTLADEN"):
    return {
        "id": id,
        "name": f"Regel {id}",
        "category": category,
        "priority": priority,
        "transaction_types": ["Buchung"],
        "services": ["Apple Pay"],
        "triggers": {
            "merchants": [merchant],
            "locations": [],
            "include_keywords": [],
            "exclude_keywords": [],
        },
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

        assert engine.rules[0].source == "base.json"

    def test_source_attribute_set_from_overlay(self, tmp_path):
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1)])
        _write(overlay, [_rule(2)])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        by_id = {r.id: r for r in engine.rules}
        assert by_id[1].source == "base.json"
        assert by_id[2].source == "overlay.json"

    def test_source_updated_on_override(self, tmp_path):
        """When an overlay overrides a base rule, source reflects the overlay file."""
        base = tmp_path / "base.json"
        overlay = tmp_path / "overlay.json"
        _write(base, [_rule(1, category="Alt")])
        _write(overlay, [_rule(1, category="Neu")])

        engine = RuleEngine(str(base), overlay_path=str(overlay))

        rule = next(r for r in engine.rules if r.id == 1)
        assert rule.source == "overlay.json"

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

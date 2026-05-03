#!/usr/bin/env python3
"""Tests for explain_rule_match tool."""

import os
import sys
from pathlib import Path

# Add root and src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from rule_engine import RuleEngine
from explain_rule_match import build_explain_report, _render_text_report


def test_rule_explain_match_matches_boolean_result():
    """Rule.explain_match should stay consistent with Rule.matches."""
    txns = ImportHandler.load_csv('data/example/input/export.202503.csv')
    engine = RuleEngine('data/example/rules.json')

    txn = txns[0]
    rule = engine.rules[0]

    explanation = rule.explain_match(txn)

    assert "matched" in explanation
    assert "checks" in explanation
    assert "failed_checks" in explanation
    assert explanation["matched"] == rule.matches(txn)
    assert isinstance(explanation["checks"], list)


def test_build_explain_report_for_line_selection():
    """Report should be generated when selecting by input file + line number."""
    txns = ImportHandler.load_csv('data/example/input/export.202503.csv')
    sample_txn = txns[0]

    report = build_explain_report(
        run_dir=Path('data/example'),
        transaction_id=None,
        line_number=sample_txn.source_line_number,
        input_file='export.202503.csv',
        rule_id=None,
        no_overlays=False,
        no_overrides=False,
        max_non_matching=3,
    )

    assert report["transaction"]["source_line_number"] == sample_txn.source_line_number
    assert report["transaction"]["input_file"] == 'input/export.202503.csv'
    assert "matched_rules" in report
    assert "non_matching_candidates" in report


def test_build_explain_report_for_target_rule():
    """Target rule diagnostics should be included when rule_id is provided."""
    txns = ImportHandler.load_csv('data/example/input/export.202503.csv')
    engine = RuleEngine('data/example/rules.json')

    sample_txn = txns[0]
    target_rule = engine.rules[0]

    report = build_explain_report(
        run_dir=Path('data/example'),
        transaction_id=None,
        line_number=sample_txn.source_line_number,
        input_file='export.202503.csv',
        rule_id=target_rule.key,
        no_overlays=False,
        no_overrides=False,
        max_non_matching=3,
    )

    assert report["target_rule"] is not None
    assert report["target_rule"]["key"] == target_rule.key
    assert isinstance(report["target_rule"]["checks"], list)
    assert len(report["target_rule"]["checks"]) > 0


def test_build_explain_report_uses_overlay_declared_key_for_overrides():
    """Overlay rules should be reported under their declared overlay key."""
    report = build_explain_report(
        run_dir=Path('data/private/dev'),
        transaction_id=None,
        line_number=9,
        input_file='privates_konto.202501.csv',
        rule_id='housing_1_private',
        no_overlays=False,
        no_overrides=False,
        max_non_matching=3,
    )

    assert report["pre_override"]["winning_rule"] == 'housing_1_private'
    assert report["pre_override"]["winning_rule_source"].endswith('data/private/dev/rules.json')
    assert report["target_rule"] is not None
    assert report["target_rule"]["key"] == 'housing_1_private'
    assert report["target_rule"]["source"].endswith('data/private/dev/rules.json')
    assert report["pre_override"]["winning_rule_layer"] == 'overlay'
    assert report["pre_override"]["winning_rule_overlay_of"] == 'housing_1'

    text_report = _render_text_report(report)
    assert "Rule Layer: overlay" in text_report
    assert "Overlay Of: housing_1" in text_report


def test_build_explain_report_can_disable_overlays():
    """Disabling overlays should make overlay-only rule IDs unavailable."""
    try:
        build_explain_report(
            run_dir=Path('data/private/dev'),
            transaction_id=None,
            line_number=9,
            input_file='privates_konto.202501.csv',
            rule_id='housing_1_private',
            no_overlays=True,
            no_overrides=False,
            max_non_matching=3,
        )
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Unknown rule ID" in str(e)


def test_build_explain_report_requires_exactly_one_selector():
    """Caller must provide either transaction_id or line_number selector."""
    try:
        build_explain_report(
            run_dir=Path('data/example'),
            transaction_id=None,
            line_number=None,
            input_file=None,
            rule_id=None,
            no_overlays=False,
            no_overrides=False,
            max_non_matching=3,
        )
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Specify exactly one selector" in str(e)

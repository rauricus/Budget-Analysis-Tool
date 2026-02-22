#!/usr/bin/env python3
import sys, os
os.chdir('/Users/andreas/budget-tool')
sys.path.insert(0, '/Users/andreas/budget-tool/src')

from rule_engine import RuleEngine

engine = RuleEngine('data/rules.json')

# Find rules
for rule in engine.rules:
    if rule.id in ['kiosk', 'byro', 'coop_supermarket']:
        print(f"\nRule: {rule.id} (priority={rule.priority})")
        print(f"  merchants: {rule.merchants}")
        print(f"  locations: {rule.locations}")
        print(f"  include_keywords: {rule.include_keywords}")
        print(f"  exclude_keywords: {rule.exclude_keywords}")

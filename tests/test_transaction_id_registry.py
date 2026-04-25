#!/usr/bin/env python3
"""Tests for transaction ID registry behavior."""
import copy
import sys
import os
import tempfile
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from transaction_id_registry import TransactionIdRegistry


def test_assigns_ids_and_persists_registry():
    """Assigned IDs should be stable across registry reloads."""
    txns = ImportHandler.load_csv('data/example/input/export.202503.csv')

    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'transaction_id_registry.json'

        registry = TransactionIdRegistry(registry_path)
        registry.assign_batch(txns)
        first_run_ids = [txn.transaction_id for txn in txns]
        registry.save()

        txns_again = ImportHandler.load_csv('data/example/input/export.202503.csv')
        registry_reloaded = TransactionIdRegistry(registry_path)
        registry_reloaded.assign_batch(txns_again)
        second_run_ids = [txn.transaction_id for txn in txns_again]

        assert all(first_run_ids), 'All transactions should receive an ID'
        assert first_run_ids == second_run_ids, 'IDs should stay stable across runs'


def test_duplicate_transactions_get_distinct_ids():
    """Exact duplicates in one batch should still receive different IDs."""
    txns = ImportHandler.load_csv('data/example/input/export.202503.csv')

    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / 'transaction_id_registry.json'
        registry = TransactionIdRegistry(registry_path)

        duplicate_a = txns[0]
        duplicate_b = copy.copy(txns[0])
        registry.assign_batch([duplicate_a, duplicate_b])

        assert duplicate_a.transaction_id != duplicate_b.transaction_id

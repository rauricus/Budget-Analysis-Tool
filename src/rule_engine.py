import json
from pathlib import Path
from typing import Optional
from models import Rule, Transaction


class RuleEngine:
    """Lädt Rules aus JSON und matched sie gegen Transaktionen"""
    
    def __init__(self, rules_path: str = "data/rules.json"):
        self.rules_path = Path(rules_path)
        self.rules: list[Rule] = []
        self.fallback_category: str = "Sonstiges"
        self.load_rules()
    
    def load_rules(self):
        """Rules aus JSON laden"""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules-Datei nicht gefunden: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.fallback_category = data.get("fallback_category", "Sonstiges")
        
        # Rules parsen
        for rule_data in data.get("rules", []):
            rule = Rule(
                id=rule_data["id"],
                name=rule_data["name"],
                category=rule_data["category"],
                priority=rule_data["priority"],
                transaction_types=rule_data.get("transaction_types", []),
                merchants=rule_data["triggers"].get("merchants", []),
                locations=rule_data["triggers"].get("locations", []),
                include_keywords=rule_data["triggers"].get("include_keywords", []),
                exclude_keywords=rule_data["triggers"].get("exclude_keywords", []),
            )
            self.rules.append(rule)
        
        # Nach Priorität sortieren (absteigend)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        print(f"✅ {len(self.rules)} Regeln geladen (sortiert nach Priorität)")
    
    def categorize(self, transaction: Transaction) -> str:
        """
        Findet die beste Regel für eine Transaktion.
        Gibt die Kategorie zurück (oder fallback_category).
        """
        for rule in self.rules:
            if rule.matches(transaction):
                return rule.category
        
        return self.fallback_category
    
    def categorize_batch(self, transactions: list[Transaction]) -> tuple[list[Transaction], dict]:
        """
        Kategorisiert eine Liste von Transaktionen.
        Modifiziert jede Transaktion in-place (kategorie_auto).
        
        Returns:
            (categorized_transactions, matching_rules_map)
            matching_rules_map: {transaction_index: [matching_rules]}
        """
        matching_rules_map = {}
        for idx, txn in enumerate(transactions):
            # Finde alle matching rules (sortiert nach Priorität)
            matching = [r for r in self.rules if r.matches(txn)]
            matching_rules_map[idx] = matching
            
            # Kategorisiere
            txn.kategorie_auto = self.categorize(txn)
        
        return transactions, matching_rules_map

"""Domain models.

Keeps public imports stable via `from models import Transaction, Rule`.
"""

from models.rule import Rule
from models.transaction import Transaction

__all__ = ["Transaction", "Rule"]
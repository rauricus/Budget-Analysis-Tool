"""Notification parsing package.

Public API is exposed via NotificationTextParser facade.
Service-specific parser strategies live under notification.parsers.
"""

from notification.base import NotificationParseResult, AbstractServiceParser
from notification.facade import NotificationTextParser
from notification.registry import NotificationParserRegistry

__all__ = [
    "AbstractServiceParser",
    "NotificationParseResult",
    "NotificationParserRegistry",
    "NotificationTextParser",
]
"""Notification parsing package.

Public API is exposed via NotificationTextParser facade.
Service-specific parser strategies live under notification.parsers.
"""

from notification.base import NotificationParseResult, ServiceParser
from notification.facade import NotificationTextParser
from notification.registry import NotificationParserRegistry

__all__ = [
    "ServiceParser",
    "NotificationParseResult",
    "NotificationParserRegistry",
    "NotificationTextParser",
]
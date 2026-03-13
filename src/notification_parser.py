"""Compatibility facade for notification text parsing.

New service parsers live under `parsers/` and are resolved via the registry.
This class remains a stable entry point for existing callers.
"""

from parsers.registry import NotificationParserRegistry


class NotificationTextParser:
    """Public adapter for service-based notification text parsing."""

    _registry = NotificationParserRegistry()

    @staticmethod
    def parse(avisierungstext: str) -> dict[str, str]:
        """
        Parse fields from notification text via the parser registry.

        Returns:
            {
                "service_type": str,
                "card_number": str,
                "merchant": str,
                "location": str,
            }
        """
        return NotificationTextParser._registry.parse(avisierungstext).to_dict()

"""Kompatibilitäts-Fassade für Avisierungstext-Parsing.

Neue Service-Parser leben unter `parsers/` und werden über die Registry aufgelöst.
Diese Klasse bleibt als stabiler Einstiegspunkt für bestehende Aufrufer erhalten.
"""

from parsers.registry import NotificationParserRegistry


class NotificationTextParser:
    """Öffentlicher Adapter für servicebasiertes Avisierungstext-Parsing."""

    _registry = NotificationParserRegistry()

    @staticmethod
    def parse(avisierungstext: str) -> dict[str, str]:
        """
        Parsed Felder aus Avisierungstext über die Parser-Registry.

        Returns:
            {
                "service_type": str,
                "card_number": str,
                "merchant": str,
                "location": str,
            }
        """
        return NotificationTextParser._registry.parse(avisierungstext).to_dict()

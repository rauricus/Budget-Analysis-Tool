#!/usr/bin/env python3
"""Test parser facade, registry, and service strategies."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.facade import NotificationTextParser
from notification.parsers.apple_pay_parser import ApplePayParser
from notification.registry import NotificationParserRegistry


def test_apple_pay_service_parser_supports():
    """ApplePayParser should detect Apple Pay notification texts"""
    parser = ApplePayParser()
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 30.03.2025 KARTEN NR. XXXX4821 BYRO BASEL SCHWEIZ"

    assert parser.supports(text), "Apple Pay parser should support valid Apple Pay text"


def test_registry_delegates_to_apple_pay_parser():
    """Registry should delegate to ApplePayParser and return parsed fields"""
    registry = NotificationParserRegistry()
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 CITY TANKSTELLE OLTEN WAREN 10.34"

    result = registry.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == "Apple Pay"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "CITY TANKSTELLE"
    assert result.location == "OLTEN"


def test_notification_text_parser_facade_api_contract():
    """Facade API should return dict and delegate through the registry."""
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 KKIOSK 45810 BERN SCHWEIZ"
    parsed = NotificationTextParser.parse(text)

    assert isinstance(parsed, dict), "Facade should return dict"
    assert parsed["service_type"] == "Karteneinkauf"
    assert parsed["provider"] == "Apple Pay"
    assert parsed["card_number"] == "XXXX4821"
    assert parsed["merchant"] == "KKIOSK 45810"
    assert parsed["location"] == "BERN"


if __name__ == '__main__':
    test_apple_pay_service_parser_supports()
    test_registry_delegates_to_apple_pay_parser()
    test_notification_text_parser_facade_api_contract()
    print("✓ All parser facade and registry tests passed")

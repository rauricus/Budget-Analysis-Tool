"""Public facade for service-based notification text parsing.

Keeps a stable, simple API for callers while delegating to the
service parser registry.
"""
from typing import Optional

from notification.base import NotificationParseResult, AbstractServiceParser

from notification.parsers.bank_package_fee_parser import BankPackageFeeParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.efinance_purchase_parser import EFinancePurchaseParser
from notification.parsers.credit_transfer_parser import CreditTransferParser
from notification.parsers.account_transfer_parser import AccountTransferParser
from notification.parsers.standing_order_parser import StandingOrderParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.twint_receive_parser import TwintReceiveParser
from notification.parsers.twint_purchase_parser import TwintPurchaseParser
from notification.parsers.payment_parser import PaymentParser



class NoNotificationParserFoundError(Exception):
    """Raised by the parser registry when no service parser recognises a notification text.
    """

    def __init__(self, notification_text: str) -> None:
        super().__init__(f"No parser found for: {notification_text!r}")
        self.notification_text = notification_text
        

class _NotificationParserRegistry:
    """Registry for service-specific notification text parsers."""

    def __init__(self, parsers: Optional[list[AbstractServiceParser]] = None):
        self.parsers = parsers or [
            CardPurchaseParser(),
            EFinancePurchaseParser(),
            CashWithdrawalParser(),
            CreditTransferParser(),
            AccountTransferParser(),
            BankPackageFeeParser(),
            TwintSendParser(),
            TwintReceiveParser(),
            TwintPurchaseParser(),
            DebitDirectParser(),
            StandingOrderParser(),
            PaymentParser(),
        ]

    def parse(self, avisierungstext: str) -> NotificationParseResult:
        text = (avisierungstext or "").strip()
        if not text:
            return NotificationParseResult()

        for parser in self.parsers:
            if parser.supports(text):
                return parser.parse(text)

        raise NoNotificationParserFoundError(text)


class NotificationTextParser:
    """Public adapter for service-based notification text parsing."""

    _registry = _NotificationParserRegistry()

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
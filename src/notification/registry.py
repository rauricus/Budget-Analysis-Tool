import logging
from typing import Optional

from notification.base import NotificationParseResult, AbstractServiceParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.standing_order_parser import StandingOrderParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.payment_parser import PaymentParser


logger = logging.getLogger(__name__)


class NotificationParserRegistry:
    """Registry for service-specific notification text parsers."""

    def __init__(self, parsers: Optional[list[AbstractServiceParser]] = None):
        self.parsers = parsers or [
            CardPurchaseParser(),
            CashWithdrawalParser(),
            TwintSendParser(),
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

        logger.warning("No ServiceParser match for notification text: %s", text)

        return NotificationParseResult()

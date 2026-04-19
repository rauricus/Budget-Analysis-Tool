"""Service-specific notification parser strategies."""

from notification.parsers.bank_package_fee_parser import BankPackageFeeParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.credit_transfer_parser import CreditTransferParser
from notification.parsers.standing_order_parser import StandingOrderParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.twint_receive_parser import TwintReceiveParser
from notification.parsers.payment_parser import PaymentParser

__all__ = [
    "BankPackageFeeParser",
    "CashWithdrawalParser",
    "CardPurchaseParser",
    "CreditTransferParser",
    "TwintSendParser",
    "TwintReceiveParser",
    "DebitDirectParser",
    "StandingOrderParser",
    "PaymentParser",
]
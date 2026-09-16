"""Service-specific notification parser strategies."""

from notification.parsers.bank_package_fee_parser import BankPackageFeeParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.efinance_purchase_parser import EFinancePurchaseParser
from notification.parsers.postfinance_card_refund_parser import PostFinanceCardRefundParser
from notification.parsers.online_shopping_refund_parser import OnlineShoppingRefundParser
from notification.parsers.credit_transfer_parser import CreditTransferParser
from notification.parsers.account_transfer_parser import AccountTransferParser
from notification.parsers.standing_order_parser import StandingOrderParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.twint_receive_parser import TwintReceiveParser
from notification.parsers.twint_purchase_parser import TwintPurchaseParser
from notification.parsers.payment_parser import PaymentParser
from notification.parsers.foreign_payment_parser import ForeignPaymentParser

__all__ = [
    "BankPackageFeeParser",
    "CashWithdrawalParser",
    "CardPurchaseParser",
    "EFinancePurchaseParser",
    "PostFinanceCardRefundParser",
    "OnlineShoppingRefundParser",
    "CreditTransferParser",
    "AccountTransferParser",
    "TwintSendParser",
    "TwintReceiveParser",
    "TwintPurchaseParser",
    "DebitDirectParser",
    "StandingOrderParser",
    "PaymentParser",
    "ForeignPaymentParser",
]
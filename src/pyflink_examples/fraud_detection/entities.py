"""
Fraud Detection 도메인 엔티티

Transaction과 Alert 데이터 클래스를 정의합니다.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    """
    거래 정보를 나타내는 데이터 클래스

    Attributes:
        account_id: 계정 ID
        timestamp: 거래 발생 시각 (밀리초 단위 Unix timestamp)
        amount: 거래 금액 (USD)
    """

    account_id: int
    timestamp: int
    amount: float

    def __str__(self) -> str:
        return f"Transaction(account_id={self.account_id}, amount=${self.amount:.2f}, timestamp={self.timestamp})"


@dataclass
class Alert:
    """
    사기 거래 경고를 나타내는 데이터 클래스

    Attributes:
        account_id: 경고가 발생한 계정 ID
        message: 경고 메시지
    """

    account_id: int
    message: str

    def __str__(self) -> str:
        return f"Alert(account_id={self.account_id}, message='{self.message}')"


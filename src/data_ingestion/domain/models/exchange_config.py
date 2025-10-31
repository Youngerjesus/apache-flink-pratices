"""
거래소 연결 설정 모델

거래소 WebSocket 연결 및 API 호출에 필요한 설정을 담는 불변 도메인 모델입니다.
업비트 Idle Timeout, Rate Limit 등의 비즈니스 규칙을 반영합니다.
"""

from dataclasses import dataclass, field
from typing import Set
from urllib.parse import urlparse

from data_ingestion.domain.exceptions import InvalidConfigurationError


@dataclass(frozen=True)
class ExchangeConfig:
    """
    거래소 연결 및 데이터 수집을 위한 설정을 담는 불변 객체입니다.

    Attributes:
        exchange_name: 거래소의 이름 (예: "upbit", "bithumb").
        websocket_url: WebSocket 연결을 위한 URL.
        rest_api_url: REST API 호출을 위한 기본 URL.
        subscribed_markets: 구독할 마켓 코드의 집합 (예: {"KRW-BTC", "KRW-ETH"}).
        ping_interval_seconds: WebSocket 연결 유지(ping) 간격 (초).
                            Upbit의 Idle Timeout(120초)을 고려하여 60초 이상 권장.
        max_reconnect_attempts: 재연결 시도 최대 횟수. 0이면 무한 재시도.
        exponential_backoff_max_seconds: 지수 백오프 재시도 시 최대 대기 시간 (초).
    """

    exchange_name: str
    websocket_url: str
    rest_api_url: str
    subscribed_markets: Set[str] = field(default_factory=set)
    ping_interval_seconds: int = 60
    max_reconnect_attempts: int = 10
    exponential_backoff_max_seconds: int = 60

    def __post_init__(self) -> None:
        """객체 생성 후 불변 필드에 대한 추가 검증 및 정규화를 수행합니다."""
        # subscribed_markets 정규화: 항상 대문자로 변환
        normalized_markets = {market.upper() for market in self.subscribed_markets}
        object.__setattr__(self, "subscribed_markets", frozenset(normalized_markets))

        self.validate()

    def validate(self) -> None:
        """
        설정 값의 유효성을 검사합니다.

        Raises:
            InvalidConfigurationError: 설정이 유효하지 않을 경우 발생합니다.
        """
        errors = []

        if not self.exchange_name or not isinstance(self.exchange_name, str):
            errors.append("exchange_name must be a non-empty string.")

        if not self._is_valid_url(self.websocket_url):
            errors.append(f"Invalid websocket_url format: {self.websocket_url}")

        if not self._is_valid_url(self.rest_api_url):
            errors.append(f"Invalid rest_api_url format: {self.rest_api_url}")

        if not self.subscribed_markets:
            errors.append("subscribed_markets cannot be empty.")

        if self.ping_interval_seconds < 60:
            errors.append("ping_interval_seconds must be at least 60 seconds for Upbit compatibility.")

        if self.max_reconnect_attempts < 0:
            errors.append("max_reconnect_attempts cannot be negative.")

        if self.exponential_backoff_max_seconds < 1:
            errors.append("exponential_backoff_max_seconds must be at least 1 second.")

        if errors:
            raise InvalidConfigurationError(
                f"ExchangeConfig validation failed for {self.exchange_name}: "
                f"{'; '.join(errors)}"
            )

    def _is_valid_url(self, url: str) -> bool:
        """주어진 문자열이 유효한 URL 형식인지 검사합니다."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def get_unique_markets(self) -> frozenset[str]:
        """
        구독할 마켓의 중복 제거된 집합을 반환합니다.
        
        Returns:
            중복이 제거되고 정규화된(대문자) 마켓 코드 집합
        """
        return self.subscribed_markets

    def is_infinite_reconnect(self) -> bool:
        """
        무한 재연결 모드 여부를 반환합니다.
        
        max_reconnect_attempts가 0이면 무한 재시도를 의미합니다.
        
        Returns:
            무한 재연결 모드이면 True, 그렇지 않으면 False
        """
        return self.max_reconnect_attempts == 0

    def __str__(self) -> str:
        """객체의 사용자 친화적인 문자열 표현을 반환합니다."""
        return (
            f"ExchangeConfig(exchange_name={self.exchange_name}, "
            f"websocket_url={self.websocket_url}, "
            f"subscribed_markets={len(self.subscribed_markets)} markets)"
        )

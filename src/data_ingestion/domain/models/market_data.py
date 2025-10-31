"""
시장 데이터 메시지 모델

거래소로부터 수신한 시장 데이터를 표현하는 불변 도메인 모델입니다.
데이터 무결성과 비즈니스 규칙 준수를 보장합니다.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from datetime import UTC

from data_ingestion.domain.exceptions import ValidationException


class MarketDataType(Enum):
    """시장 데이터의 타입을 정의합니다."""

    TRADE = "trade"
    ORDERBOOK = "orderbook"


class StreamType(Enum):
    """
    스트림 데이터 타입

    거래소로부터 수신하는 데이터의 종류를 구분합니다.

    Attributes:
        SNAPSHOT: 초기 스냅샷 데이터 (전체 호가창 등)
        REALTIME: 실시간 업데이트 데이터 (증분 변경분)

    Examples:
        >>> stream_type = StreamType.REALTIME
        >>> stream_type.name
        'REALTIME'
    """

    SNAPSHOT = "snapshot"
    REALTIME = "realtime"


@dataclass(frozen=True)
class MarketDataMessage:
    """
    시장 데이터 메시지

    거래소로부터 수신한 원시 시장 데이터를 담는 불변 객체입니다.
    모든 필드는 생성 후 변경할 수 없으며, 비즈니스 규칙 검증을 제공합니다.

    Attributes:
        exchange: 거래소 식별자 (예: "upbit", "bithumb")
        _code: 마켓 코드 (예: "KRW-BTC", "KRW-ETH") - 내부 필드, code property 사용 권장
        received_timestamp: 데이터 수신 시각 (UTC, timezone-aware datetime)
        event_timestamp: 원본 이벤트 발생 시각 (UTC, timezone-aware datetime)
        stream_type: 스트림 타입 (SNAPSHOT 또는 REALTIME)
        raw_data: 원시 데이터 딕셔너리 (거래소별 형식, deep copy 보관)

    Examples:
        >>> from datetime import datetime, UTC
        >>> message = MarketDataMessage(
        ...     exchange="upbit",
        ...     code="krw-btc",
        ...     received_timestamp=datetime.now(UTC),
        ...     event_timestamp=datetime.now(UTC),
        ...     stream_type=StreamType.REALTIME,
        ...     raw_data={"price": 50000000, "volume": 1.5}
        ... )
        >>> message.validate()  # 검증 성공
        >>> message.code  # 자동으로 정규화됨
        'KRW-BTC'
    """

    exchange: str
    data_type: MarketDataType
    _code: str
    received_timestamp: datetime
    event_timestamp: datetime
    stream_type: StreamType
    _raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    def __init__(
        self,
        exchange: str,
        code: str,
        received_timestamp: datetime,
        event_timestamp: datetime = None,
        stream_type: StreamType = StreamType.REALTIME,
        raw_data: dict[str, Any] = None,
        data_type: MarketDataType = MarketDataType.TRADE,
    ):
        """
        MarketDataMessage 생성자

        Args:
            exchange: 거래소 식별자
            data_type: 데이터 타입 (TRADE or ORDERBOOK)
            code: 마켓 코드 (자동으로 정규화됨)
            received_timestamp: 데이터 수신 시각 (UTC)
            event_timestamp: 원본 이벤트 발생 시각 (UTC, 기본값: received_timestamp)
            stream_type: 스트림 타입 (기본값: REALTIME)
            raw_data: 원시 데이터 딕셔너리 (deep copy로 보관됨, 기본값: 빈 dict)
        """
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "data_type", data_type)
        object.__setattr__(self, "_code", code)
        object.__setattr__(self, "received_timestamp", received_timestamp)
        object.__setattr__(self, "event_timestamp", event_timestamp or received_timestamp)
        object.__setattr__(self, "stream_type", stream_type)
        object.__setattr__(self, "_raw_data", deepcopy(raw_data if raw_data else {}))

    @property
    def code(self) -> str:
        """
        정규화된 마켓 코드 반환

        Returns:
            대문자로 정규화된 마켓 코드

        Examples:
            >>> from datetime import datetime, UTC
            >>> message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="krw-btc",
            ...     received_timestamp=datetime.now(UTC),
            ...     event_timestamp=datetime.now(UTC),
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> message.code
            'KRW-BTC'
        """
        return self._code.upper()

    @property
    def raw_data(self) -> dict[str, Any]:
        """
        원시 데이터 딕셔너리 반환

        Returns:
            원시 데이터 딕셔너리 (읽기 전용)
        """
        return self._raw_data

    def validate(self) -> None:
        """
        비즈니스 규칙 검증

        다음 규칙을 검증합니다:
        - exchange가 비어있지 않아야 함
        - code가 'KRW-' prefix로 시작해야 함 (업비트 규칙)
        - received_timestamp와 event_timestamp가 timezone-aware (UTC)여야 함
        - event_timestamp가 received_timestamp보다 미래가 아니어야 함
        - raw_data가 비어있지 않아야 함

        Raises:
            ValidationException: 검증 실패 시

        Examples:
            >>> from datetime import datetime, UTC
            >>> # 올바른 메시지
            >>> now = datetime.now(UTC)
            >>> message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="KRW-BTC",
            ...     received_timestamp=now,
            ...     event_timestamp=now,
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> message.validate()  # OK

            >>> # 잘못된 코드 형식
            >>> invalid_message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="BTC-KRW",  # 잘못된 형식
            ...     received_timestamp=now,
            ...     event_timestamp=now,
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> invalid_message.validate()  # Raises ValidationException
            Traceback (most recent call last):
                ...
            ValidationException: Invalid market code...
        """
        errors = []

        # exchange 검증
        if not self.exchange or not self.exchange.strip():
            errors.append("exchange cannot be empty")

        # code 검증 (업비트 형식: KRW-XXX)
        if not self.code.upper().startswith("KRW-"):
            errors.append(
                f"Invalid market code: '{self.code}' "
                f"(expected format: KRW-XXX for Upbit)"
            )

        # received_timestamp timezone 검증
        received_tz_valid = True
        if self.received_timestamp.tzinfo != UTC:
            received_tz_valid = False
            if self.received_timestamp.tzinfo is None:
                errors.append("received_timestamp must be timezone-aware (UTC)")
            else:
                errors.append(
                    f"received_timestamp must be UTC, got {self.received_timestamp.tzinfo}"
                )

        # event_timestamp timezone 검증
        event_tz_valid = True
        if self.event_timestamp.tzinfo != UTC:
            event_tz_valid = False
            if self.event_timestamp.tzinfo is None:
                errors.append("event_timestamp must be timezone-aware (UTC)")
            else:
                errors.append(
                    f"event_timestamp must be UTC, got {self.event_timestamp.tzinfo}"
                )

        # event_timestamp는 received_timestamp보다 미래일 수 없음 (타임존이 유효한 경우만 비교)
        if received_tz_valid and event_tz_valid:
            if self.event_timestamp > self.received_timestamp:
                errors.append(
                    f"event_timestamp ({self.event_timestamp}) cannot be later than "
                    f"received_timestamp ({self.received_timestamp})"
                )

        # raw_data 검증
        if not self.raw_data:
            errors.append("raw_data cannot be empty")

        if errors:
            raise ValidationException(
                f"MarketDataMessage validation failed: {'; '.join(errors)}"
            )

    def normalize_code(self) -> str:
        """
        마켓 코드 정규화 (deprecated: code property 사용 권장)

        소문자를 대문자로 변환하여 정규화된 마켓 코드를 반환합니다.
        이제 code property가 자동으로 정규화를 수행하므로 이 메서드는 호환성을 위해 유지됩니다.

        Returns:
            정규화된 마켓 코드 (대문자)

        Examples:
            >>> from datetime import datetime, UTC
            >>> now = datetime.now(UTC)
            >>> message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="krw-btc",
            ...     received_timestamp=now,
            ...     event_timestamp=now,
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> message.normalize_code()
            'KRW-BTC'
            >>> message.code  # 동일한 결과
            'KRW-BTC'
        """
        return self.code

    def __repr__(self) -> str:
        """
        문자열 표현

        디버깅에 유용한 주요 필드를 포함한 표현을 반환합니다.

        Returns:
            문자열 표현

        Examples:
            >>> from datetime import datetime, UTC
            >>> now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            >>> message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="KRW-BTC",
            ...     received_timestamp=now,
            ...     event_timestamp=now,
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> "upbit" in repr(message)
            True
            >>> "KRW-BTC" in repr(message)
            True
        """
        return (
            f"MarketDataMessage(exchange='{self.exchange}', "
            f"code='{self.code}', "
            f"received_timestamp={self.received_timestamp.isoformat()}, "
            f"event_timestamp={self.event_timestamp.isoformat()}, "
            f"stream_type={self.stream_type.name})"
        )


"""
MarketDataMessage 시장 데이터 메시지 테스트

이 테스트 모듈은 거래소로부터 수신한 시장 데이터 메시지를 검증합니다.
불변성, 비즈니스 규칙 준수, 데이터 정규화를 엄격하게 검증합니다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from data_ingestion.domain.exceptions import ValidationException
from data_ingestion.domain.models.market_data import MarketDataMessage, StreamType


class TestMarketDataMessageImmutability:
    """MarketDataMessage 불변성 테스트"""

    def test_message_is_frozen(self) -> None:
        """
        GIVEN: MarketDataMessage 인스턴스
        WHEN: 속성을 수정하려고 시도할 때
        THEN: 불변성이 보장되어 수정이 거부되어야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN - 속성 수정 시도 시 에러 발생
        with pytest.raises((AttributeError, TypeError)):
            message._code = "KRW-ETH"  # type: ignore

    def test_message_raw_data_is_immutable(self) -> None:
        """
        GIVEN: MarketDataMessage 인스턴스
        WHEN: raw_data 딕셔너리를 외부에서 수정하려고 시도할 때
        THEN: 원본 데이터는 deep copy로 보호되어 영향을 받지 않아야 함
        """
        # GIVEN
        original_data = {"price": 50000000, "volume": 1.5}
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data=original_data,
        )

        # WHEN - 원본 딕셔너리 수정
        original_data["price"] = 60000000

        # THEN - 메시지의 데이터는 deep copy로 보호되어 영향받지 않음
        assert message.raw_data["price"] == 50000000


class TestMarketDataMessageValidation:
    """MarketDataMessage 검증 로직 테스트"""

    def test_valid_market_code_format(self) -> None:
        """
        GIVEN: 올바른 형식의 마켓 코드 (KRW-XXX)
        WHEN: MarketDataMessage를 생성할 때
        THEN: 검증에 성공해야 함
        """
        # GIVEN / WHEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # THEN - 검증 성공
        message.validate()

    def test_invalid_market_code_format_rejects(self) -> None:
        """
        GIVEN: 잘못된 형식의 마켓 코드 (KRW- prefix 없음)
        WHEN: MarketDataMessage를 생성하고 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="BTC-KRW",  # 잘못된 형식
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "KRW-" in str(exc_info.value)
        assert "BTC-KRW" in str(exc_info.value)

    def test_empty_raw_data_rejects(self) -> None:
        """
        GIVEN: 빈 raw_data 딕셔너리
        WHEN: MarketDataMessage를 생성하고 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={},  # 빈 딕셔너리
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "raw_data" in str(exc_info.value)
        assert "empty" in str(exc_info.value).lower()

    def test_lowercase_code_gets_normalized(self) -> None:
        """
        GIVEN: 소문자 마켓 코드
        WHEN: code property를 조회할 때
        THEN: 대문자로 자동 변환되어야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="krw-btc",  # 소문자
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN - code property가 자동으로 정규화
        assert message.code == "KRW-BTC"

    def test_already_uppercase_code_unchanged(self) -> None:
        """
        GIVEN: 이미 대문자인 마켓 코드
        WHEN: code property를 조회할 때
        THEN: 그대로 반환되어야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        assert message.code == "KRW-BTC"

    def test_event_timestamp_later_than_received_timestamp_rejected(self) -> None:
        """
        GIVEN: event_timestamp가 received_timestamp보다 미래인 경우
        WHEN: MarketDataMessage를 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        future = now + timedelta(seconds=10)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=future,  # 미래 시각
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "event_timestamp" in str(exc_info.value)
        assert "received_timestamp" in str(exc_info.value)


class TestMarketDataMessageTimezone:
    """MarketDataMessage 타임존 검증 테스트"""

    def test_timestamps_are_utc(self) -> None:
        """
        GIVEN: UTC 타임존의 datetime
        WHEN: MarketDataMessage를 생성할 때
        THEN: 타임존이 UTC로 유지되어야 함
        """
        # GIVEN
        utc_time = datetime.now(UTC)

        # WHEN
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=utc_time,
            event_timestamp=utc_time,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # THEN
        assert message.received_timestamp.tzinfo == UTC
        assert message.event_timestamp.tzinfo == UTC

    def test_naive_received_timestamp_rejected(self) -> None:
        """
        GIVEN: 타임존 정보가 없는 naive received_timestamp
        WHEN: MarketDataMessage를 생성하고 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        naive_time = datetime.now()  # 타임존 없음
        utc_time = datetime.now(UTC)

        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=naive_time,
            event_timestamp=utc_time,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "received_timestamp" in str(exc_info.value)
        assert "timezone" in str(exc_info.value).lower() or "UTC" in str(exc_info.value)

    def test_naive_event_timestamp_rejected(self) -> None:
        """
        GIVEN: 타임존 정보가 없는 naive event_timestamp
        WHEN: MarketDataMessage를 생성하고 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        naive_time = datetime.now()  # 타임존 없음
        utc_time = datetime.now(UTC)

        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=utc_time,
            event_timestamp=naive_time,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "event_timestamp" in str(exc_info.value)
        assert "timezone" in str(exc_info.value).lower() or "UTC" in str(exc_info.value)


class TestMarketDataMessageStreamType:
    """MarketDataMessage StreamType 검증 테스트"""

    def test_snapshot_stream_type(self) -> None:
        """
        GIVEN: StreamType.SNAPSHOT
        WHEN: MarketDataMessage를 생성할 때
        THEN: 정상적으로 생성되어야 함
        """
        # GIVEN / WHEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.SNAPSHOT,
            raw_data={"price": 50000000},
        )

        # THEN
        assert message.stream_type == StreamType.SNAPSHOT

    def test_realtime_stream_type(self) -> None:
        """
        GIVEN: StreamType.REALTIME
        WHEN: MarketDataMessage를 생성할 때
        THEN: 정상적으로 생성되어야 함
        """
        # GIVEN / WHEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # THEN
        assert message.stream_type == StreamType.REALTIME


class TestMarketDataMessageExchangeField:
    """MarketDataMessage exchange 필드 검증 테스트"""

    def test_upbit_exchange(self) -> None:
        """
        GIVEN: 'upbit' exchange
        WHEN: MarketDataMessage를 생성할 때
        THEN: 정상적으로 생성되어야 함
        """
        # GIVEN / WHEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # THEN
        assert message.exchange == "upbit"

    def test_empty_exchange_rejected(self) -> None:
        """
        GIVEN: 빈 exchange 문자열
        WHEN: MarketDataMessage를 생성하고 검증할 때
        THEN: ValidationException이 발생해야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="",  # 빈 문자열
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(ValidationException) as exc_info:
            message.validate()

        assert "exchange" in str(exc_info.value)


class TestMarketDataMessageEquality:
    """MarketDataMessage 동등성 비교 테스트"""

    def test_same_data_equals(self) -> None:
        """
        GIVEN: 동일한 데이터를 가진 두 MarketDataMessage
        WHEN: 비교할 때
        THEN: 동일한 것으로 인식되어야 함
        """
        # GIVEN
        timestamp = datetime.now(UTC)
        message1 = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=timestamp,
            event_timestamp=timestamp,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )
        message2 = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=timestamp,
            event_timestamp=timestamp,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        assert message1 == message2

    def test_different_data_not_equals(self) -> None:
        """
        GIVEN: 다른 데이터를 가진 두 MarketDataMessage
        WHEN: 비교할 때
        THEN: 다른 것으로 인식되어야 함
        """
        # GIVEN
        timestamp = datetime.now(UTC)
        message1 = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=timestamp,
            event_timestamp=timestamp,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )
        message2 = MarketDataMessage(
            exchange="upbit",
            code="KRW-ETH",  # 다른 코드
            received_timestamp=timestamp,
            event_timestamp=timestamp,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        assert message1 != message2


class TestMarketDataMessageRepresentation:
    """MarketDataMessage 문자열 표현 테스트"""

    def test_repr_includes_key_fields(self) -> None:
        """
        GIVEN: MarketDataMessage 인스턴스
        WHEN: repr()을 호출할 때
        THEN: 주요 필드들이 포함된 문자열이 반환되어야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN
        repr_str = repr(message)

        # THEN
        assert "upbit" in repr_str
        assert "KRW-BTC" in repr_str
        assert "MarketDataMessage" in repr_str
        assert "received_timestamp" in repr_str
        assert "event_timestamp" in repr_str


class TestMarketDataMessageCodeProperty:
    """MarketDataMessage code property 테스트"""

    def test_code_property_normalizes_automatically(self) -> None:
        """
        GIVEN: 소문자 마켓 코드로 생성된 메시지
        WHEN: code property를 조회할 때
        THEN: 자동으로 대문자로 정규화되어야 함
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="krw-eth",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 3000000},
        )

        # WHEN / THEN
        assert message.code == "KRW-ETH"

    def test_normalize_code_method_compatibility(self) -> None:
        """
        GIVEN: 소문자 마켓 코드로 생성된 메시지
        WHEN: normalize_code() 메서드를 호출할 때
        THEN: code property와 동일한 결과를 반환해야 함 (하위 호환성)
        """
        # GIVEN
        now = datetime.now(UTC)
        message = MarketDataMessage(
            exchange="upbit",
            code="krw-xrp",
            received_timestamp=now,
            event_timestamp=now,
            stream_type=StreamType.REALTIME,
            raw_data={"price": 500},
        )

        # WHEN / THEN
        assert message.normalize_code() == message.code
        assert message.normalize_code() == "KRW-XRP"

"""
MessagePublisher 인터페이스 테스트

이 테스트 모듈은 MessagePublisher 포트 인터페이스의 계약을 검증합니다.
모든 메시지 발행 구현체는 이 인터페이스 계약을 준수해야 합니다.
"""

import inspect

import pytest

from data_ingestion.domain.exceptions import PublishException
from data_ingestion.domain.models.market_data import MarketDataMessage, StreamType
from data_ingestion.domain.ports.message_publisher import MessagePublisher


class TestMessagePublisherInterfaceStructure:
    """MessagePublisher 인터페이스 구조 테스트"""

    def test_message_publisher_is_abstract(self) -> None:
        """
        GIVEN: MessagePublisher 클래스
        WHEN: 직접 인스턴스화를 시도할 때
        THEN: TypeError가 발생해야 함 (추상 클래스)
        """
        # WHEN / THEN
        with pytest.raises(TypeError):
            MessagePublisher()  # type: ignore

    def test_message_publisher_has_required_methods(self) -> None:
        """
        GIVEN: MessagePublisher 인터페이스
        WHEN: 인터페이스 메서드를 확인할 때
        THEN: 모든 필수 메서드가 정의되어 있어야 함
        """
        # GIVEN
        required_methods = ["publish", "flush", "close"]

        # WHEN / THEN
        for method_name in required_methods:
            assert hasattr(MessagePublisher, method_name)
            method = getattr(MessagePublisher, method_name)
            assert callable(method)

    def test_publish_is_async(self) -> None:
        """
        GIVEN: MessagePublisher.publish 메서드
        WHEN: 메서드를 확인할 때
        THEN: async 메서드여야 함
        """
        # WHEN
        method = getattr(MessagePublisher, "publish")

        # THEN
        assert inspect.iscoroutinefunction(method)

    def test_flush_is_async(self) -> None:
        """
        GIVEN: MessagePublisher.flush 메서드
        WHEN: 메서드를 확인할 때
        THEN: async 메서드여야 함
        """
        # WHEN
        method = getattr(MessagePublisher, "flush")

        # THEN
        assert inspect.iscoroutinefunction(method)

    def test_close_is_async(self) -> None:
        """
        GIVEN: MessagePublisher.close 메서드
        WHEN: 메서드를 확인할 때
        THEN: async 메서드여야 함
        """
        # WHEN
        method = getattr(MessagePublisher, "close")

        # THEN
        assert inspect.iscoroutinefunction(method)


class MockMessagePublisher(MessagePublisher):
    """MessagePublisher 인터페이스의 테스트용 Mock 구현체"""

    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self._published_messages: list[MarketDataMessage] = []
        self._is_closed = False
        self._flush_count = 0

    async def publish(self, message: MarketDataMessage) -> None:
        """메시지 발행 시뮬레이션"""
        if self._is_closed:
            raise PublishException("Publisher is closed")

        if self._should_fail:
            raise PublishException("Failed to publish message (mock failure)")

        self._published_messages.append(message)

    async def flush(self) -> None:
        """flush 시뮬레이션"""
        if self._is_closed:
            raise PublishException("Publisher is closed")

        self._flush_count += 1

    async def close(self) -> None:
        """close 시뮬레이션"""
        self._is_closed = True


class TestMessagePublisherInterfaceContract:
    """MessagePublisher 인터페이스 계약 테스트"""

    @pytest.mark.asyncio
    async def test_mock_publisher_implements_interface(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: 인터페이스를 구현할 때
        THEN: 모든 추상 메서드가 구현되어야 함
        """
        # GIVEN / WHEN
        publisher = MockMessagePublisher()

        # THEN
        assert isinstance(publisher, MessagePublisher)

    @pytest.mark.asyncio
    async def test_publish_sends_message(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: publish()를 호출할 때
        THEN: 메시지가 발행되어야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher()
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN
        await publisher.publish(message)

        # THEN
        assert len(publisher._published_messages) == 1
        assert publisher._published_messages[0] == message

    @pytest.mark.asyncio
    async def test_publish_is_idempotent(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: 동일한 메시지를 여러 번 발행할 때
        THEN: 각 호출이 독립적으로 처리되어야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher()
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN
        await publisher.publish(message)
        await publisher.publish(message)
        await publisher.publish(message)

        # THEN - 3번 모두 발행됨
        assert len(publisher._published_messages) == 3

    @pytest.mark.asyncio
    async def test_publish_failure_raises_exception(self) -> None:
        """
        GIVEN: 실패하도록 설정된 MockMessagePublisher
        WHEN: publish()를 호출할 때
        THEN: PublishException이 발생해야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher(should_fail=True)
        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(PublishException):
            await publisher.publish(message)

    @pytest.mark.asyncio
    async def test_flush_completes_successfully(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: flush()를 호출할 때
        THEN: 성공적으로 완료되어야 함
        """
        # GIVEN
        publisher = MockMessagePublisher()

        # WHEN
        await publisher.flush()

        # THEN
        assert publisher._flush_count == 1

    @pytest.mark.asyncio
    async def test_close_marks_publisher_as_closed(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: close()를 호출할 때
        THEN: publisher가 닫힌 상태로 표시되어야 함
        """
        # GIVEN
        publisher = MockMessagePublisher()

        # WHEN
        await publisher.close()

        # THEN
        assert publisher._is_closed

    @pytest.mark.asyncio
    async def test_publish_after_close_raises_exception(self) -> None:
        """
        GIVEN: 닫힌 MockMessagePublisher
        WHEN: publish()를 호출할 때
        THEN: PublishException이 발생해야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher()
        await publisher.close()

        message = MarketDataMessage(
            exchange="upbit",
            code="KRW-BTC",
            received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
            stream_type=StreamType.REALTIME,
            raw_data={"price": 50000000},
        )

        # WHEN / THEN
        with pytest.raises(PublishException) as exc_info:
            await publisher.publish(message)

        assert "closed" in str(exc_info.value).lower()


class TestMessagePublisherBatchOperations:
    """MessagePublisher 배치 작업 테스트"""

    @pytest.mark.asyncio
    async def test_multiple_messages_can_be_published(self) -> None:
        """
        GIVEN: MockMessagePublisher 구현체
        WHEN: 여러 메시지를 연속으로 발행할 때
        THEN: 모든 메시지가 성공적으로 발행되어야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher()
        messages = [
            MarketDataMessage(
                exchange="upbit",
                code=f"KRW-BTC{i}",
                received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data={"price": 50000000 + i * 1000},
            )
            for i in range(10)
        ]

        # WHEN
        for message in messages:
            await publisher.publish(message)

        # THEN
        assert len(publisher._published_messages) == 10

    @pytest.mark.asyncio
    async def test_flush_after_multiple_publishes(self) -> None:
        """
        GIVEN: 여러 메시지를 발행한 MockMessagePublisher
        WHEN: flush()를 호출할 때
        THEN: 성공적으로 완료되어야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        publisher = MockMessagePublisher()
        for i in range(5):
            message = MarketDataMessage(
                exchange="upbit",
                code="KRW-BTC",
                received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data={"price": 50000000 + i * 1000},
            )
            await publisher.publish(message)

        # WHEN
        await publisher.flush()

        # THEN
        assert publisher._flush_count == 1
        assert len(publisher._published_messages) == 5



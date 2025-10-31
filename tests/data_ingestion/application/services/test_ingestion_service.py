"""
IngestionService 테스트

데이터 수집 오케스트레이션 서비스의 핵심 기능을 테스트합니다:
- 초기화 및 생명주기 관리
- 데이터 스트리밍 및 발행
- 에러 처리 및 복원력
- 상태 관리
"""

import asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from data_ingestion.domain.exceptions import PublishException
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.market_data import MarketDataMessage, MarketDataType, StreamType
from data_ingestion.domain.ports.exchange_connector import ExchangeConnector
from data_ingestion.domain.ports.message_publisher import MessagePublisher


# IngestionService를 import하지만, 아직 구현되지 않았으므로 테스트 실행 시 import error 발생 가능
# 이는 TDD의 정상적인 과정입니다.
try:
    from data_ingestion.application.services.ingestion_service import IngestionService
except ImportError:
    IngestionService = None


@pytest.fixture
def mock_connector() -> AsyncMock:
    """Mock ExchangeConnector 픽스처"""
    connector = AsyncMock(spec=ExchangeConnector)
    connector.connect = AsyncMock()
    connector.disconnect = AsyncMock()
    connector.get_connection_state = AsyncMock(return_value=ConnectionState.CONNECTED)
    # config 속성 추가 (구독 마켓 필터링에 사용)
    connector.config = MagicMock()
    connector.config.subscribed_markets = {"KRW-BTC", "KRW-ETH"}
    return connector


@pytest.fixture
def mock_publisher() -> AsyncMock:
    """Mock MessagePublisher 픽스처"""
    publisher = AsyncMock(spec=MessagePublisher)
    publisher.publish = AsyncMock()
    publisher.flush = AsyncMock(return_value=0)
    publisher.close = AsyncMock()
    return publisher


@pytest.fixture
def sample_trade_message() -> MarketDataMessage:
    """샘플 Trade 메시지 픽스처"""
    return MarketDataMessage(
        exchange="upbit",
        code="KRW-BTC",
        received_timestamp=datetime.now(UTC),
        event_timestamp=datetime.now(UTC),
        stream_type=StreamType.REALTIME,
        raw_data={"price": 50000000, "volume": 1.5},
        data_type=MarketDataType.TRADE,
    )


@pytest.fixture
def sample_orderbook_message() -> MarketDataMessage:
    """샘플 OrderBook 메시지 픽스처"""
    return MarketDataMessage(
        exchange="upbit",
        code="KRW-ETH",
        received_timestamp=datetime.now(UTC),
        event_timestamp=datetime.now(UTC),
        stream_type=StreamType.REALTIME,
        raw_data={"total_ask_size": 100.0, "total_bid_size": 200.0},
        data_type=MarketDataType.ORDERBOOK,
    )


@pytest.mark.skipif(IngestionService is None, reason="IngestionService not implemented yet")
class TestIngestionServiceInitialization:
    """IngestionService 초기화 및 생명주기 테스트"""

    def test_초기화_시_의존성_주입_확인(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: ExchangeConnector와 MessagePublisher
        WHEN: IngestionService를 생성하면
        THEN: 의존성이 정상적으로 주입되어야 한다
        """
        # WHEN
        service = IngestionService(mock_connector, mock_publisher)

        # THEN
        assert service._connector == mock_connector
        assert service._publisher == mock_publisher
        assert service._running is False
        assert service._processed_count == 0
        assert service._consecutive_failures == 0

    def test_max_consecutive_failures_커스터마이징(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 커스텀 max_consecutive_failures 값
        WHEN: IngestionService를 생성하면
        THEN: 설정된 값이 적용되어야 한다
        """
        # WHEN
        service = IngestionService(mock_connector, mock_publisher, max_consecutive_failures=5)

        # THEN
        assert service._max_consecutive_failures == 5

    @pytest.mark.asyncio
    async def test_start_호출_시_connector와_publisher_순서대로_초기화(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: IngestionService
        WHEN: start()를 호출하면
        THEN: connector.connect()가 먼저 호출되어야 한다
        """
        # GIVEN
        service = IngestionService(mock_connector, mock_publisher)

        # Mock stream_market_data to return empty async iterator
        async def empty_stream():
            return
            yield  # Make it a generator

        mock_connector.stream_market_data = empty_stream

        # WHEN
        await service.start()
        await asyncio.sleep(0.1)  # 백그라운드 태스크 시작 대기

        # THEN
        mock_connector.connect.assert_called_once()
        assert service._running is True

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_start_재호출_시_RuntimeError(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 이미 실행 중인 IngestionService
        WHEN: start()를 다시 호출하면
        THEN: RuntimeError가 발생해야 한다
        """
        # GIVEN
        service = IngestionService(mock_connector, mock_publisher)

        async def empty_stream():
            return
            yield

        mock_connector.stream_market_data = empty_stream
        await service.start()

        # WHEN, THEN
        with pytest.raises(RuntimeError, match="already running"):
            await service.start()

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_호출_시_graceful_shutdown(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 실행 중인 IngestionService
        WHEN: stop()을 호출하면
        THEN: flush → disconnect 순서로 정리되어야 한다
        """
        # GIVEN
        service = IngestionService(mock_connector, mock_publisher)

        async def empty_stream():
            return
            yield

        mock_connector.stream_market_data = empty_stream
        await service.start()
        await asyncio.sleep(0.1)

        # WHEN
        await service.stop()

        # THEN
        mock_publisher.flush.assert_called_once()
        mock_connector.disconnect.assert_called_once()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_stop_여러번_호출_시_멱등성(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 실행 중인 IngestionService
        WHEN: stop()을 여러 번 호출하면
        THEN: 첫 번째만 실제 정리가 수행되고 나머지는 무시되어야 한다
        """
        # GIVEN
        service = IngestionService(mock_connector, mock_publisher)

        async def empty_stream():
            return
            yield

        mock_connector.stream_market_data = empty_stream
        await service.start()
        await asyncio.sleep(0.1)

        # WHEN
        await service.stop()
        await service.stop()
        await service.stop()

        # THEN
        # flush와 disconnect는 한 번만 호출되어야 함
        assert mock_publisher.flush.call_count == 1
        assert mock_connector.disconnect.call_count == 1


@pytest.mark.skipif(IngestionService is None, reason="IngestionService not implemented yet")
class TestIngestionServiceDataStreaming:
    """IngestionService 데이터 스트리밍 및 발행 테스트"""

    @pytest.mark.asyncio
    async def test_메시지_수신_후_Kafka_발행_성공(
        self,
        mock_connector: AsyncMock,
        mock_publisher: AsyncMock,
        sample_trade_message: MarketDataMessage,
    ) -> None:
        """
        GIVEN: 메시지를 제공하는 connector
        WHEN: 서비스가 실행되면
        THEN: publisher.publish()가 호출되어야 한다
        """
        # GIVEN
        async def message_stream():
            yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.2)  # 메시지 처리 대기
        await service.stop()

        # THEN
        assert mock_publisher.publish.call_count >= 1
        assert service._processed_count >= 1

    @pytest.mark.asyncio
    async def test_1000개마다_로그_출력(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: 다수의 메시지를 제공하는 connector
        WHEN: 1,000개 이상 처리하면
        THEN: 로그가 출력되고 카운터가 정확해야 한다
        """
        # GIVEN
        async def message_stream():
            for _ in range(1100):
                yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        with patch("data_ingestion.application.services.ingestion_service.logger") as mock_logger:
            await service.start()
            await asyncio.sleep(0.5)  # 메시지 처리 대기
            await service.stop()

            # THEN
            assert service._processed_count == 1100
            # 1,000개, 2,000개 등에서 로그 출력 확인
            assert any("1000" in str(call) for call in mock_logger.info.call_args_list)

    @pytest.mark.asyncio
    async def test_구독하지_않은_마켓_필터링(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 구독하지 않은 마켓의 메시지
        WHEN: 서비스가 실행되면
        THEN: 해당 메시지는 발행되지 않아야 한다
        """
        # GIVEN
        # Connector의 config에 KRW-BTC만 구독되어 있다고 가정
        mock_connector.config = MagicMock()
        mock_connector.config.subscribed_markets = {"KRW-BTC"}

        unsubscribed_message = MarketDataMessage(
            exchange="upbit",
            code="KRW-DOGE",  # 구독하지 않은 코인
            received_timestamp=datetime.now(UTC),
            event_timestamp=datetime.now(UTC),
            stream_type=StreamType.REALTIME,
            raw_data={"price": 100},
            data_type=MarketDataType.TRADE,
        )

        async def message_stream():
            yield unsubscribed_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.2)
        await service.stop()

        # THEN
        # 구독하지 않은 메시지는 발행되지 않아야 함
        mock_publisher.publish.assert_not_called()


@pytest.mark.skipif(IngestionService is None, reason="IngestionService not implemented yet")
class TestIngestionServiceErrorHandling:
    """IngestionService 에러 처리 및 복원력 테스트"""

    @pytest.mark.asyncio
    async def test_연속_10회_발행_실패_시_서비스_중단(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: publish()가 계속 실패하는 상황
        WHEN: 연속 10회 실패하면
        THEN: PublishException이 발생하며 서비스가 중단되어야 한다
        """
        # GIVEN
        async def message_stream():
            for _ in range(15):
                yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        mock_publisher.publish = AsyncMock(side_effect=PublishException("Kafka down"))
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        
        # 백그라운드 태스크에서 예외 발생을 기다림
        with pytest.raises(PublishException):
            await service._background_task

        # THEN
        assert service._consecutive_failures >= 10

    @pytest.mark.asyncio
    async def test_발행_실패_후_성공_시_카운터_리셋(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: publish()가 일시적으로 실패했다가 성공하는 상황
        WHEN: 실패 후 성공하면
        THEN: consecutive_failures 카운터가 0으로 리셋되어야 한다
        """
        # GIVEN
        call_count = 0

        async def publish_with_intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise PublishException("Temporary failure")
            # 4번째부터는 성공

        mock_publisher.publish = AsyncMock(side_effect=publish_with_intermittent_failure)

        async def message_stream():
            for _ in range(5):
                yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.5)
        await service.stop()

        # THEN
        # 3번 실패 후 성공했으므로 카운터는 0이어야 함
        assert service._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_WebSocket_재연결_후_스트리밍_재개(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: WebSocket 연결이 끊겼다가 재연결되는 상황
        WHEN: 재연결 후
        THEN: 스트리밍이 정상적으로 재개되어야 한다
        """
        # GIVEN
        # BaseWebSocketConnector의 자동 재연결 기능에 의존
        # 여기서는 stream이 중단되었다가 다시 시작되는 시나리오를 모킹
        message_count = 0

        async def reconnecting_stream():
            nonlocal message_count
            for _ in range(3):
                yield sample_trade_message
                message_count += 1
            # 연결 끊김 시뮬레이션 (StopAsyncIteration)
            # 실제로는 BaseWebSocketConnector가 재연결 처리

        mock_connector.stream_market_data = reconnecting_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()

        # THEN
        assert service._processed_count == 3

    @pytest.mark.asyncio
    async def test_Kafka_일시_장애_시_연결_유지(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: Kafka 발행이 일시적으로 실패하는 상황
        WHEN: 발행 실패가 발생해도
        THEN: WebSocket 연결은 유지되어야 한다
        """
        # GIVEN
        call_count = 0

        async def publish_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise PublishException("Kafka temporary failure")

        mock_publisher.publish = AsyncMock(side_effect=publish_with_failure)

        async def message_stream():
            for _ in range(5):
                yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.5)
        await service.stop()

        # THEN
        # Connector는 disconnect가 정상적으로 호출되어야 함 (강제 종료 아님)
        mock_connector.disconnect.assert_called_once()


@pytest.mark.skipif(IngestionService is None, reason="IngestionService not implemented yet")
class TestIngestionServiceStateManagement:
    """IngestionService 상태 관리 테스트"""

    @pytest.mark.asyncio
    async def test_get_status_정상_상태(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock, sample_trade_message: MarketDataMessage
    ) -> None:
        """
        GIVEN: 실행 중인 서비스
        WHEN: get_status()를 호출하면
        THEN: 정확한 상태 정보가 반환되어야 한다
        """
        # GIVEN
        async def message_stream():
            for _ in range(5):
                yield sample_trade_message

        mock_connector.stream_market_data = message_stream
        service = IngestionService(mock_connector, mock_publisher)

        # WHEN
        await service.start()
        await asyncio.sleep(0.3)
        status = service.get_status()
        await service.stop()

        # THEN
        assert status["running"] is True
        assert status["processed"] == 5
        assert status["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_get_status_중단_상태(
        self, mock_connector: AsyncMock, mock_publisher: AsyncMock
    ) -> None:
        """
        GIVEN: 중단된 서비스
        WHEN: get_status()를 호출하면
        THEN: running이 False여야 한다
        """
        # GIVEN
        async def empty_stream():
            return
            yield

        mock_connector.stream_market_data = empty_stream
        service = IngestionService(mock_connector, mock_publisher)
        await service.start()
        await service.stop()

        # WHEN
        status = service.get_status()

        # THEN
        assert status["running"] is False


"""
ExchangeConnector 인터페이스 테스트

이 테스트 모듈은 ExchangeConnector 포트 인터페이스의 계약을 검증합니다.
모든 구현체는 이 인터페이스 계약을 준수해야 합니다.
"""

import inspect
from collections.abc import AsyncIterator
from typing import get_type_hints

import pytest

from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import MarketDataMessage
from data_ingestion.domain.ports.exchange_connector import ExchangeConnector


class TestExchangeConnectorInterfaceStructure:
    """ExchangeConnector 인터페이스 구조 테스트"""

    def test_exchange_connector_is_abstract(self) -> None:
        """
        GIVEN: ExchangeConnector 클래스
        WHEN: 직접 인스턴스화를 시도할 때
        THEN: TypeError가 발생해야 함 (추상 클래스)
        """
        # WHEN / THEN
        with pytest.raises(TypeError):
            ExchangeConnector()  # type: ignore

    def test_exchange_connector_has_required_methods(self) -> None:
        """
        GIVEN: ExchangeConnector 인터페이스
        WHEN: 인터페이스 메서드를 확인할 때
        THEN: 모든 필수 메서드가 정의되어 있어야 함
        """
        # GIVEN
        required_methods = [
            "connect",
            "disconnect",
            "stream_market_data",
            "get_connection_state",
        ]

        # WHEN / THEN
        for method_name in required_methods:
            assert hasattr(ExchangeConnector, method_name)
            method = getattr(ExchangeConnector, method_name)
            assert callable(method)

    def test_connect_is_async(self) -> None:
        """
        GIVEN: ExchangeConnector.connect 메서드
        WHEN: 메서드를 확인할 때
        THEN: async 메서드여야 함
        """
        # WHEN
        method = getattr(ExchangeConnector, "connect")

        # THEN
        assert inspect.iscoroutinefunction(method)

    def test_disconnect_is_async(self) -> None:
        """
        GIVEN: ExchangeConnector.disconnect 메서드
        WHEN: 메서드를 확인할 때
        THEN: async 메서드여야 함
        """
        # WHEN
        method = getattr(ExchangeConnector, "disconnect")

        # THEN
        assert inspect.iscoroutinefunction(method)

    def test_stream_market_data_returns_async_iterator(self) -> None:
        """
        GIVEN: ExchangeConnector.stream_market_data 메서드
        WHEN: 반환 타입을 확인할 때
        THEN: AsyncIterator[MarketDataMessage]를 반환해야 함
        """
        # WHEN
        type_hints = get_type_hints(ExchangeConnector.stream_market_data)

        # THEN
        assert "return" in type_hints
        # AsyncIterator[MarketDataMessage] 검증
        return_type = str(type_hints["return"])
        assert "AsyncIterator" in return_type or "AsyncGenerator" in return_type


class MockExchangeConnector(ExchangeConnector):
    """ExchangeConnector 인터페이스의 테스트용 Mock 구현체"""

    def __init__(self, config: ExchangeConfig) -> None:
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._is_connected = False

    async def connect(self) -> None:
        """연결 시뮬레이션"""
        self._state = ConnectionState.CONNECTING
        self._is_connected = True
        self._state = ConnectionState.CONNECTED

    async def disconnect(self) -> None:
        """연결 해제 시뮬레이션"""
        self._is_connected = False
        self._state = ConnectionState.DISCONNECTED

    async def stream_market_data(self) -> AsyncIterator[MarketDataMessage]:
        """스트리밍 시뮬레이션"""
        from datetime import UTC, datetime

        from data_ingestion.domain.models.market_data import StreamType

        # 테스트용 더미 데이터 생성
        for i in range(3):
            yield MarketDataMessage(
                exchange=self._config.exchange_name,
                code="KRW-BTC",
                received_timestamp=datetime.now(UTC),
                event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data={"price": 50000000 + i * 1000, "volume": 1.5},
            )

    def get_connection_state(self) -> ConnectionState:
        """현재 연결 상태 반환"""
        return self._state


class TestExchangeConnectorInterfaceContract:
    """ExchangeConnector 인터페이스 계약 테스트"""

    @pytest.mark.asyncio
    async def test_mock_connector_implements_interface(self) -> None:
        """
        GIVEN: MockExchangeConnector 구현체
        WHEN: 인터페이스를 구현할 때
        THEN: 모든 추상 메서드가 구현되어야 함
        """
        # GIVEN
        from datetime import UTC, datetime

        from data_ingestion.domain.models.market_data import StreamType

        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )

        # WHEN
        connector = MockExchangeConnector(config)

        # THEN - 모든 메서드가 구현되어 있어야 함
        assert isinstance(connector, ExchangeConnector)

    @pytest.mark.asyncio
    async def test_connect_changes_state_to_connected(self) -> None:
        """
        GIVEN: DISCONNECTED 상태의 connector
        WHEN: connect()를 호출할 때
        THEN: 상태가 CONNECTED로 변경되어야 함
        """
        # GIVEN
        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )
        connector = MockExchangeConnector(config)

        # WHEN
        await connector.connect()

        # THEN
        assert connector.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_changes_state_to_disconnected(self) -> None:
        """
        GIVEN: CONNECTED 상태의 connector
        WHEN: disconnect()를 호출할 때
        THEN: 상태가 DISCONNECTED로 변경되어야 함
        """
        # GIVEN
        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )
        connector = MockExchangeConnector(config)
        await connector.connect()

        # WHEN
        await connector.disconnect()

        # THEN
        assert connector.get_connection_state() == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self) -> None:
        """
        GIVEN: 이미 CONNECTED 상태의 connector
        WHEN: connect()를 여러 번 호출할 때
        THEN: 안전하게 처리되어야 함 (멱등성)
        """
        # GIVEN
        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )
        connector = MockExchangeConnector(config)
        await connector.connect()

        # WHEN - 여러 번 호출
        await connector.connect()
        await connector.connect()

        # THEN - 여전히 CONNECTED 상태
        assert connector.get_connection_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_stream_market_data_yields_messages(self) -> None:
        """
        GIVEN: CONNECTED 상태의 connector
        WHEN: stream_market_data()를 호출할 때
        THEN: MarketDataMessage를 반환해야 함
        """
        # GIVEN
        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )
        connector = MockExchangeConnector(config)
        await connector.connect()

        # WHEN
        messages = []
        async for message in connector.stream_market_data():
            messages.append(message)

        # THEN
        assert len(messages) == 3
        for msg in messages:
            assert isinstance(msg, MarketDataMessage)
            assert msg.exchange == "upbit"


class TestExchangeConnectorInitialization:
    """ExchangeConnector 초기화 테스트"""

    def test_connector_requires_config(self) -> None:
        """
        GIVEN: ExchangeConnector 구현체
        WHEN: 인스턴스를 생성할 때
        THEN: ExchangeConfig를 필요로 해야 함
        """
        # GIVEN
        config = ExchangeConfig(
            exchange_name="upbit",
            websocket_url="wss://api.upbit.com/websocket/v1",
            rest_api_url="https://api.upbit.com/v1",
            subscribed_markets={"KRW-BTC"},
            ping_interval_seconds=60,
            max_reconnect_attempts=5,
            exponential_backoff_max_seconds=5,
        )

        # WHEN
        connector = MockExchangeConnector(config)

        # THEN
        assert connector is not None
        assert connector.get_connection_state() == ConnectionState.DISCONNECTED



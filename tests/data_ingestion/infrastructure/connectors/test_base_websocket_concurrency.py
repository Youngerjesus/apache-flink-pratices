"""
BaseWebSocketConnector 동시성 제어 테스트

Race Condition 방지를 위한 동시성 제어 검증:
- 동시 connect() 호출 시 단일 연결만 수립
- 더블 체크 패턴으로 불필요한 연결 회피
- 단일 비행(single-flight) 패턴으로 중복 연결 방지
"""

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, patch, call

import pytest

from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import MarketDataMessage, MarketDataType, StreamType
from data_ingestion.infrastructure.connectors.base_websocket import BaseWebSocketConnector


class ConcurrencyTestConnector(BaseWebSocketConnector):
    """동시성 테스트용 WebSocket 커넥터 구현"""

    async def _send_subscription_message(self) -> None:
        """테스트용 빈 구독 메시지"""
        pass

    async def _parse_message(self, raw_message: str) -> Dict[str, Any] | None:
        """테스트용 간단한 파싱"""
        return {"type": "test", "data": raw_message}

    def _convert_to_market_data_messages(
        self, parsed_data: Dict[str, Any]
    ) -> list[MarketDataMessage]:
        """테스트용 메시지 변환"""
        return [
            MarketDataMessage(
                exchange=self._config.exchange_name,
                code="TEST",
                received_timestamp=datetime.now(UTC),
                event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data=parsed_data,
                data_type=MarketDataType.TRADE,
            )
        ]


@pytest.fixture
def test_config() -> ExchangeConfig:
    """테스트용 설정"""
    return ExchangeConfig(
        exchange_name="test_exchange",
        websocket_url="wss://test.example.com/ws",
        rest_api_url="https://test.example.com",
        subscribed_markets={"TEST-MARKET"},
        ping_interval_seconds=60,
        max_reconnect_attempts=3,
        exponential_backoff_max_seconds=10,
    )


@pytest.fixture
def connector(test_config: ExchangeConfig) -> ConcurrencyTestConnector:
    """테스트용 커넥터"""
    return ConcurrencyTestConnector(test_config)


class TestConcurrentConnect:
    """동시 connect() 호출 처리 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_connect_calls_only_connect_once(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: BaseWebSocketConnector
        WHEN: 여러 코루틴이 동시에 connect()를 호출하면
        THEN: websockets.connect는 1회만 호출되어야 한다 (단일 비행 패턴)
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            # 연결 시뮬레이션: 약간의 지연 추가하여 동시성 테스트
            async def mock_connect_func(*args, **kwargs):
                await asyncio.sleep(0.05)  # 50ms 지연
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            # WHEN - 3개의 코루틴이 동시에 connect 호출
            results = await asyncio.gather(
                connector.connect(),
                connector.connect(),
                connector.connect(),
                return_exceptions=True
            )

            # THEN - websockets.connect는 1회만 호출
            assert mock_connect.call_count == 1
            
            # 모든 호출이 성공
            assert all(result is None for result in results if not isinstance(result, Exception))
            
            # 연결 상태 확인
            assert connector.get_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_idempotent_connect_returns_immediately_if_connected(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: 이미 연결된 WebSocket
        WHEN: connect()를 다시 호출하면
        THEN: 즉시 반환되어야 하고 websockets.connect는 호출되지 않아야 한다
        """
        # GIVEN - 첫 번째 연결
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            await connector.connect()
            assert mock_connect.call_count == 1
            
            # WHEN - 이미 연결된 상태에서 다시 connect 호출
            await connector.connect()
            await connector.connect()
            
            # THEN - websockets.connect는 1회만 호출 (추가 호출 없음)
            assert mock_connect.call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_connect_during_connecting_state(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: 연결 중인 WebSocket (CONNECTING 상태)
        WHEN: 다른 코루틴이 connect()를 호출하면
        THEN: 첫 번째 연결이 완료될 때까지 대기하고, websockets.connect는 1회만 호출되어야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            # 연결에 충분한 시간이 걸리도록 설정
            async def mock_connect_func(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms 지연
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            # WHEN - 첫 번째 연결 시작
            task1 = asyncio.create_task(connector.connect())
            
            # 약간 대기 후 CONNECTING 상태인지 확인
            await asyncio.sleep(0.02)
            
            # 두 번째, 세 번째 연결 시도
            task2 = asyncio.create_task(connector.connect())
            task3 = asyncio.create_task(connector.connect())
            
            # 모든 태스크 완료 대기
            await asyncio.gather(task1, task2, task3, return_exceptions=True)

            # THEN - websockets.connect는 1회만 호출
            assert mock_connect.call_count == 1
            
            # 연결 상태 확인
            assert connector.get_state() == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_no_race_condition_on_state_transition(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: 여러 코루틴이 동시에 connect() 호출
        WHEN: 상태 전환이 발생할 때
        THEN: 상태 전환이 원자적으로 처리되어 일관성이 유지되어야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            async def mock_connect_func(*args, **kwargs):
                await asyncio.sleep(0.05)
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            # WHEN - 동시에 10개의 connect 호출
            tasks = [connector.connect() for _ in range(10)]
            await asyncio.gather(*tasks, return_exceptions=True)

            # THEN - 상태가 일관성 있게 유지됨
            assert connector.get_state() == ConnectionState.CONNECTED
            
            # websockets.connect는 1회만 호출
            assert mock_connect.call_count == 1


class TestConcurrentDisconnect:
    """동시 disconnect() 호출 처리 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_disconnect_is_safe(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: 여러 코루틴이 동시에 disconnect()를 호출하면
        THEN: 안전하게 처리되고 리소스가 누수되지 않아야 한다
        """
        # GIVEN - 연결 수립
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            mock_websocket.close = AsyncMock()
            
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            await connector.connect()
            assert connector.get_state() == ConnectionState.CONNECTED

            # WHEN - 동시에 여러 disconnect 호출
            await asyncio.gather(
                connector.disconnect(),
                connector.disconnect(),
                connector.disconnect(),
                return_exceptions=True
            )

            # THEN - close는 1회만 호출 (또는 여러 번이라도 에러 없이 처리)
            assert connector.get_state() == ConnectionState.DISCONNECTED
            
            # WebSocket이 정리되었는지 확인
            assert connector._websocket is None


class TestConnectDisconnectRaceCondition:
    """connect와 disconnect 동시 호출 처리 테스트"""

    @pytest.mark.asyncio
    async def test_disconnect_during_connect_is_handled_safely(
        self, connector: ConcurrencyTestConnector
    ) -> None:
        """
        GIVEN: 연결 중인 WebSocket
        WHEN: 연결 중에 disconnect()가 호출되면
        THEN: 안전하게 처리되고 데드락이 발생하지 않아야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            mock_websocket.close = AsyncMock()
            
            # 연결에 시간이 걸리도록 설정
            async def mock_connect_func(*args, **kwargs):
                await asyncio.sleep(0.1)
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            # WHEN - connect 시작
            connect_task = asyncio.create_task(connector.connect())
            
            # 약간 대기 후 disconnect 호출
            await asyncio.sleep(0.02)
            disconnect_task = asyncio.create_task(connector.disconnect())
            
            # 모든 태스크 완료 대기
            await asyncio.gather(connect_task, disconnect_task, return_exceptions=True)

            # THEN - 데드락 없이 완료되어야 함
            # 최종 상태는 DISCONNECTED 또는 CONNECTED (타이밍에 따라)
            final_state = connector.get_state()
            assert final_state in (ConnectionState.DISCONNECTED, ConnectionState.CONNECTED, ConnectionState.FAILED)


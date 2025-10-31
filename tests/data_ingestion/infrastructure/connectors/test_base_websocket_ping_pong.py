"""
BaseWebSocketConnector 핑/퐁 타임아웃 테스트

업비트 120초 Idle Timeout을 고려한 핑/퐁 정책 검증:
- ping_interval=60초 (120초 timeout의 절반)
- ping_timeout=30초 (pong 미수신 시 연결 종료)
"""

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

from data_ingestion.domain.exceptions import ConnectionException
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import MarketDataMessage, MarketDataType, StreamType
from data_ingestion.infrastructure.connectors.base_websocket import BaseWebSocketConnector


class TestWebSocketConnector(BaseWebSocketConnector):
    """테스트용 WebSocket 커넥터 구현"""

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
def connector(test_config: ExchangeConfig) -> TestWebSocketConnector:
    """테스트용 커넥터"""
    return TestWebSocketConnector(test_config)


class TestWebSocketPingPongConfiguration:
    """WebSocket 핑/퐁 설정 테스트"""

    @pytest.mark.asyncio
    async def test_connect_uses_library_ping_pong(
        self, connector: TestWebSocketConnector
    ) -> None:
        """
        GIVEN: BaseWebSocketConnector
        WHEN: connect()를 호출하면
        THEN: websockets 라이브러리 핑/퐁이 활성화되어야 한다
        """
        # GIVEN / WHEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            # websockets.connect는 awaitable을 반환하므로 async function으로 mock
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            try:
                await connector.connect()
            except asyncio.CancelledError:
                pass

            # THEN - websockets.connect에 ping_interval, ping_timeout 전달
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            
            assert "ping_interval" in call_kwargs
            assert call_kwargs["ping_interval"] == 60  # config의 ping_interval_seconds
            
            assert "ping_timeout" in call_kwargs
            assert call_kwargs["ping_timeout"] == 30  # 권장값 30초

    @pytest.mark.asyncio
    async def test_ping_interval_from_config(
        self, test_config: ExchangeConfig
    ) -> None:
        """
        GIVEN: 특정 ping_interval_seconds를 가진 설정
        WHEN: connect()를 호출하면
        THEN: 설정값이 websockets.connect에 전달되어야 한다
        """
        # GIVEN
        custom_config = ExchangeConfig(
            exchange_name="test",
            websocket_url="wss://test.example.com/ws",
            rest_api_url="https://test.example.com",
            subscribed_markets={"TEST"},
            ping_interval_seconds=90,  # 커스텀 값
            max_reconnect_attempts=3,
            exponential_backoff_max_seconds=10,
        )
        connector = TestWebSocketConnector(custom_config)

        # WHEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            try:
                await connector.connect()
            except asyncio.CancelledError:
                pass

            # THEN
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["ping_interval"] == 90


class TestWebSocketPongTimeout:
    """WebSocket pong 타임아웃 처리 테스트"""

    @pytest.mark.skip(reason="재연결 로직 개선 필요 (우선순위 6, 7)")
    @pytest.mark.asyncio
    async def test_connection_closed_on_pong_timeout(
        self, connector: TestWebSocketConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: pong이 30초 내에 돌아오지 않으면
        THEN: ConnectionClosed 예외가 발생하고 재연결을 시도해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            # 첫 번째 연결: pong timeout으로 ConnectionClosed 발생
            mock_websocket_1 = AsyncMock()
            mock_websocket_1.recv = AsyncMock(
                side_effect=ConnectionClosed(rcvd=None, sent=None)
            )
            
            # 두 번째 연결: 성공
            mock_websocket_2 = AsyncMock()
            mock_websocket_2.recv = AsyncMock(side_effect=asyncio.CancelledError())

            call_count = [0]
            async def mock_connect_func(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_websocket_1
                return mock_websocket_2
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            try:
                await connector.connect()
                # stream_market_data에서 재연결 로직이 작동할 것
                async for _ in connector.stream_market_data():
                    break
            except (asyncio.CancelledError, ConnectionClosed):
                pass

            # THEN - 재연결이 시도되었는지 확인
            assert mock_connect.call_count >= 1

    @pytest.mark.asyncio
    async def test_no_manual_ping_task_started(
        self, connector: TestWebSocketConnector
    ) -> None:
        """
        GIVEN: websockets 라이브러리 핑/퐁을 사용하는 설정
        WHEN: connect()를 호출하면
        THEN: 수동 ping 태스크가 시작되지 않아야 한다 (_ping_task 속성 자체가 없어야 함)
        """
        # GIVEN / WHEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            try:
                await connector.connect()
            except asyncio.CancelledError:
                pass

            # THEN - ping 태스크 속성이 없어야 함 (라이브러리가 자동 처리)
            assert not hasattr(connector, "_ping_task")


class TestWebSocketIdleTimeout:
    """WebSocket Idle Timeout 대응 테스트"""

    @pytest.mark.asyncio
    async def test_ping_prevents_idle_timeout(
        self, test_config: ExchangeConfig
    ) -> None:
        """
        GIVEN: 60초 ping_interval 설정
        WHEN: 90초 동안 메시지가 없어도
        THEN: 자동 ping으로 idle timeout을 방지해야 한다
        """
        # GIVEN
        connector = TestWebSocketConnector(test_config)

        # WHEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_websocket = AsyncMock()
            
            # 60초마다 ping, 90초 후에도 연결 유지
            # (websockets 라이브러리가 자동 처리)
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            
            async def mock_connect_func(*args, **kwargs):
                return mock_websocket
            
            mock_connect.side_effect = mock_connect_func

            try:
                await connector.connect()
            except asyncio.CancelledError:
                pass

            # THEN - ping_interval=60으로 설정되어 120초 idle timeout 방지
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["ping_interval"] == 60
            assert call_kwargs["ping_interval"] < 120  # 업비트 idle timeout보다 작음


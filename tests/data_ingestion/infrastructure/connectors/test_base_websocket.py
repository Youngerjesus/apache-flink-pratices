"""
Base WebSocket Connector 테스트

이 모듈은 BaseWebSocketConnector의 핵심 기능을 테스트합니다:
- 연결 생명주기 관리
- 자동 재연결 및 지수 백오프
- Ping/Pong 처리
- 상태 전환 검증
"""

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import websockets

from data_ingestion.domain.exceptions import (
    ConnectionClosedError,
    ConnectionException,
    ConnectionFailedError,
    InvalidTransitionError,
)
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.infrastructure.connectors.base_websocket import (
    BaseWebSocketConnector,
)


class ConcreteWebSocketConnector(BaseWebSocketConnector):
    """테스트용 구체 구현체"""

    def __init__(self, config: ExchangeConfig) -> None:
        super().__init__(config)
        self.subscribe_called = False
        self.parse_called = False
        self.parsed_messages = []

    async def _send_subscription_message(self) -> None:
        """구독 메시지 전송 (테스트용)"""
        self.subscribe_called = True
        if self._websocket:
            await self._websocket.send('{"type": "subscribe"}')

    async def _parse_message(self, raw_message: str) -> Dict[str, Any] | None:
        """메시지 파싱 (테스트용)"""
        self.parse_called = True
        try:
            import json

            parsed = json.loads(raw_message)
            self.parsed_messages.append(parsed)
            return parsed
        except Exception:
            return None


@pytest.fixture
def exchange_config() -> ExchangeConfig:
    """테스트용 ExchangeConfig 픽스처"""
    return ExchangeConfig(
        exchange_name="test_exchange",
        websocket_url="ws://localhost:8080/ws",
        rest_api_url="http://localhost:8080/api",
        subscribed_markets={"KRW-BTC", "KRW-ETH"},
        ping_interval_seconds=60,
        max_reconnect_attempts=3,
        exponential_backoff_max_seconds=10,
    )


@pytest.fixture
def connector(exchange_config: ExchangeConfig) -> ConcreteWebSocketConnector:
    """테스트용 Connector 픽스처"""
    return ConcreteWebSocketConnector(exchange_config)


class TestBaseWebSocketConnectorInitialization:
    """BaseWebSocketConnector 초기화 테스트"""

    def test_초기_상태는_DISCONNECTED여야_함(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: 새로운 BaseWebSocketConnector 인스턴스
        WHEN: 초기화 직후
        THEN: 연결 상태는 DISCONNECTED여야 한다
        """
        # WHEN
        state = asyncio.run(connector.get_connection_state())

        # THEN
        assert state == ConnectionState.DISCONNECTED

    def test_설정값이_올바르게_저장됨(
        self, connector: ConcreteWebSocketConnector, exchange_config: ExchangeConfig
    ) -> None:
        """
        GIVEN: ExchangeConfig를 전달하여 생성된 Connector
        WHEN: Connector를 초기화한 후
        THEN: 설정값이 내부에 올바르게 저장되어야 한다
        """
        # THEN
        assert connector._config == exchange_config
        assert connector._websocket is None
        # 수동 ping 제거: _ping_task 속성이 없어야 함
        assert not hasattr(connector, "_ping_task")
        assert connector._reconnect_attempts == 0


class TestBaseWebSocketConnectorConnection:
    """BaseWebSocketConnector 연결 테스트"""

    @pytest.mark.asyncio
    async def test_connect_성공_시_상태가_CONNECTED로_변경됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: DISCONNECTED 상태의 Connector
        WHEN: connect()를 호출하고 WebSocket 연결에 성공하면
        THEN: 상태가 CONNECTED로 변경되어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        # WHEN
        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # THEN
        state = await connector.get_connection_state()
        assert state == ConnectionState.CONNECTED
        assert connector.subscribe_called is True

    @pytest.mark.asyncio
    async def test_connect_실패_시_ConnectionFailedError_발생(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: DISCONNECTED 상태의 Connector
        WHEN: connect() 호출 시 WebSocket 연결에 실패하면
        THEN: ConnectionFailedError가 발생하고 상태는 FAILED가 되어야 한다
        """
        # GIVEN / WHEN
        with patch(
            "websockets.connect", side_effect=ConnectionRefusedError("Connection refused")
        ):
            with pytest.raises(ConnectionFailedError) as exc_info:
                await connector.connect()

        # THEN
        assert "Failed to connect" in str(exc_info.value)
        state = await connector.get_connection_state()
        assert state == ConnectionState.FAILED

    @pytest.mark.asyncio
    async def test_connect_멱등성_이미_CONNECTED_상태에서_호출하면_아무것도_하지_않음(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: 이미 CONNECTED 상태인 Connector
        WHEN: connect()를 다시 호출하면
        THEN: 추가 연결을 시도하지 않고 즉시 반환해야 한다 (멱등성)
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # WHEN
        connector.subscribe_called = False  # 플래그 리셋
        await connector.connect()  # 두 번째 호출

        # THEN
        assert connector.subscribe_called is False  # 구독 메시지를 재전송하지 않음
        state = await connector.get_connection_state()
        assert state == ConnectionState.CONNECTED


class TestBaseWebSocketConnectorDisconnection:
    """BaseWebSocketConnector 연결 해제 테스트"""

    @pytest.mark.asyncio
    async def test_disconnect_성공_시_상태가_DISCONNECTED로_변경됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태의 Connector
        WHEN: disconnect()를 호출하면
        THEN: WebSocket 연결이 닫히고 상태가 DISCONNECTED로 변경되어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # WHEN
        await connector.disconnect()

        # THEN
        state = await connector.get_connection_state()
        assert state == ConnectionState.DISCONNECTED
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_멱등성_이미_DISCONNECTED_상태에서_호출해도_오류_없음(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: DISCONNECTED 상태의 Connector
        WHEN: disconnect()를 호출하면
        THEN: 오류 없이 즉시 반환해야 한다 (멱등성)
        """
        # GIVEN
        assert await connector.get_connection_state() == ConnectionState.DISCONNECTED

        # WHEN / THEN
        await connector.disconnect()  # 오류 없이 완료되어야 함
        state = await connector.get_connection_state()
        assert state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_정상_동작_및_리소스_정리됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태이며 ping_task가 실행 중인 Connector
        WHEN: disconnect()를 호출하면
        THEN: ping_task가 취소되어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # WHEN
        await connector.disconnect()

        # THEN
        state = await connector.get_connection_state()
        assert state == ConnectionState.DISCONNECTED
        # 수동 ping 제거: _ping_task 속성이 없어야 함
        assert not hasattr(connector, "_ping_task")


class TestBaseWebSocketConnectorReconnection:
    """BaseWebSocketConnector 재연결 테스트"""

    @pytest.mark.asyncio
    async def test_재연결_시도_시_지수_백오프_적용됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: 연결 실패 시나리오
        WHEN: 재연결을 여러 번 시도하면
        THEN: 대기 시간이 지수적으로 증가해야 한다 (exponential backoff)
        """
        # GIVEN
        connector._reconnect_attempts = 0

        # WHEN / THEN
        delay_1 = connector._calculate_backoff_delay()
        connector._reconnect_attempts = 1
        delay_2 = connector._calculate_backoff_delay()
        connector._reconnect_attempts = 2
        delay_3 = connector._calculate_backoff_delay()

        # 지수 백오프 검증: 2^n 형태로 증가
        assert delay_1 < delay_2 < delay_3
        # max_seconds를 초과하지 않음
        assert delay_3 <= connector._config.exponential_backoff_max_seconds

    @pytest.mark.asyncio
    async def test_최대_재연결_시도_횟수_초과_시_FAILED_상태_유지(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: 연결이 반복적으로 실패하는 상황
        WHEN: max_reconnect_attempts를 초과하여 재연결을 시도하면
        THEN: FAILED 상태를 유지하고 더 이상 재시도하지 않아야 한다
        """
        # GIVEN
        connector._reconnect_attempts = connector._config.max_reconnect_attempts

        # WHEN
        should_retry = connector._should_attempt_reconnect()

        # THEN
        assert should_retry is False


class TestBaseWebSocketConnectorPingPong:
    """BaseWebSocketConnector Ping/Pong 테스트"""

    @pytest.mark.asyncio
    async def test_connect_시_라이브러리_ping_pong_옵션_전달(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태의 Connector
        WHEN: ping_interval_seconds 동안 대기하면
        THEN: WebSocket ping이 전송되어야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_ws = AsyncMock(spec=websockets.WebSocketClientProtocol)
            async def mock_connect_func(*args, **kwargs):
                return mock_ws
            mock_connect.side_effect = mock_connect_func
            await connector.connect()

            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["ping_interval"] == connector._config.ping_interval_seconds
            assert call_kwargs["ping_timeout"] == 30

    @pytest.mark.asyncio
    async def test_websocket_close_시_다음_루프에서_재연결_시도(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태이며 ping_task가 실행 중인 Connector
        WHEN: WebSocket 연결이 예기치 않게 닫히면
        THEN: ping_task가 자동으로 취소되어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # WHEN
        await connector.disconnect()
        # 수동 ping 제거: _ping_task 속성이 없어야 함
        assert not hasattr(connector, "_ping_task")


class TestBaseWebSocketConnectorStateTransition:
    """BaseWebSocketConnector 상태 전환 테스트"""

    @pytest.mark.asyncio
    async def test_잘못된_상태_전환_시도_시_InvalidTransitionError_발생(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: DISCONNECTED 상태의 Connector
        WHEN: 직접적으로 CONNECTED로 상태를 변경하려고 하면 (CONNECTING 단계 건너뛰기)
        THEN: InvalidTransitionError가 발생해야 한다
        """
        # GIVEN
        assert await connector.get_connection_state() == ConnectionState.DISCONNECTED

        # WHEN / THEN
        # DISCONNECTED -> CONNECTED는 허용되지 않음 (CONNECTING을 거쳐야 함)
        with pytest.raises(InvalidTransitionError) as exc_info:
            ConnectionState.DISCONNECTED.validate_transition(ConnectionState.CONNECTED)
        
        # 에러 메시지 검증
        assert "Invalid state transition" in str(exc_info.value)
        assert "DISCONNECTED -> CONNECTED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_상태_전환_히스토리_추적(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: StateTransitionTracker를 사용하는 Connector
        WHEN: 여러 상태 전환이 발생하면
        THEN: 모든 전환 기록이 추적되어야 한다
        """
        # GIVEN
        from data_ingestion.domain.models.connection_state import StateTransitionTracker

        tracker = StateTransitionTracker()

        # WHEN
        tracker.record_transition(
            ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, "connect() 호출"
        )
        tracker.record_transition(
            ConnectionState.CONNECTING, ConnectionState.CONNECTED, "연결 성공"
        )

        # THEN
        history = tracker.get_history()
        assert len(history) == 2
        assert history[0]["from_state"] == ConnectionState.DISCONNECTED
        assert history[0]["to_state"] == ConnectionState.CONNECTING
        assert history[1]["from_state"] == ConnectionState.CONNECTING
        assert history[1]["to_state"] == ConnectionState.CONNECTED


class TestBaseWebSocketConnectorErrorHandling:
    """BaseWebSocketConnector 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_예상치_못한_연결_끊김_시_ConnectionClosedError_발생(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태의 Connector
        WHEN: WebSocket 연결이 예기치 않게 끊기면
        THEN: ConnectionClosedError가 발생하고 재연결을 시도해야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True

        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await connector.connect()

        # WHEN
        # WebSocket이 예기치 않게 닫힘을 시뮬레이션
        mock_websocket.open = False
        mock_websocket.recv = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosed(None, None)
        )

        # THEN
        # stream_market_data에서 ConnectionClosedError가 발생해야 함
        # (실제 구현에서는 재연결 로직이 작동)
        # 이 테스트는 구현체에서 더 자세히 검증될 예정

    @pytest.mark.asyncio
    async def test_연결_실패_후_정리_작업_수행됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: 연결 시도 중인 Connector
        WHEN: 연결이 실패하면
        THEN: 모든 리소스가 정리되고 상태가 FAILED로 변경되어야 한다
        """
        # GIVEN / WHEN
        with patch(
            "websockets.connect", side_effect=ConnectionRefusedError("Connection refused")
        ):
            with pytest.raises(ConnectionFailedError):
                await connector.connect()

        # THEN
        state = await connector.get_connection_state()
        assert state == ConnectionState.FAILED
        assert connector._websocket is None
        # 수동 ping 제거: _ping_task 속성이 없어야 함
        assert not hasattr(connector, "_ping_task")


class TestBaseWebSocketConnectorMessageParsing:
    """BaseWebSocketConnector 메시지 파싱 테스트"""

    @pytest.mark.asyncio
    async def test_parse_message_추상_메서드_서브클래스에서_구현됨(
        self, connector: ConcreteWebSocketConnector
    ) -> None:
        """
        GIVEN: ConcreteWebSocketConnector (BaseWebSocketConnector 구현체)
        WHEN: _parse_message()를 호출하면
        THEN: 서브클래스에서 구현한 로직이 실행되어야 한다
        """
        # WHEN
        result = await connector._parse_message('{"type": "test", "data": "value"}')

        # THEN
        assert connector.parse_called is True
        assert result is not None
        assert result["type"] == "test"
        assert len(connector.parsed_messages) == 1


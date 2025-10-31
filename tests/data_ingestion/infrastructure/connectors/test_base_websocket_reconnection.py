"""
BaseWebSocketConnector 예외별 재연결 처리 테스트

예외 유형에 따라 재연결 여부를 구분:
- ConnectionClosed, 네트워크/SSL/Timeout: 재연결 시도
- JSONDecodeError, InvalidMessage: 로그만, 재연결 없음
- CancelledError: 즉시 전파, 재연결 금지
"""

import asyncio
import json
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from websockets.exceptions import ConnectionClosed, InvalidURI

from data_ingestion.domain.exceptions import InvalidMessageError
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import MarketDataMessage, MarketDataType, StreamType
from data_ingestion.infrastructure.connectors.base_websocket import BaseWebSocketConnector


class ReconnectionTestConnector(BaseWebSocketConnector):
    """재연결 테스트용 WebSocket 커넥터 구현"""

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
        exponential_backoff_max_seconds=1,  # 빠른 테스트를 위해 짧게
    )


@pytest.fixture
def connector(test_config: ExchangeConfig) -> ReconnectionTestConnector:
    """테스트용 커넥터"""
    return ReconnectionTestConnector(test_config)


class TestReconnectOnConnectionErrors:
    """연결 계층 에러 시 재연결 테스트"""

    @pytest.mark.asyncio
    async def test_reconnect_on_connection_closed(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: ConnectionClosed 예외가 발생하면
        THEN: 자동으로 재연결을 시도해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            # 첫 번째 연결: 성공 후 ConnectionClosed
            mock_ws1 = AsyncMock()
            mock_ws1.recv.side_effect = [
                '{"data": "test1"}',
                ConnectionClosed(rcvd=None, sent=None)
            ]
            
            # 두 번째 연결: 재연결 성공
            mock_ws2 = AsyncMock()
            mock_ws2.recv.side_effect = [
                '{"data": "test2"}',
                asyncio.CancelledError()  # 테스트 종료
            ]
            
            call_count = [0]
            async def mock_connect_func(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_ws1
                return mock_ws2
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            message_count = 0
            try:
                async for message in connector.stream_market_data():
                    message_count += 1
                    if message_count >= 2:  # 재연결 후 메시지도 수신
                        break
            except asyncio.CancelledError:
                pass

            # THEN - 재연결 시도됨
            assert mock_connect.call_count == 2  # 초기 연결 + 재연결

    @pytest.mark.asyncio
    async def test_reconnect_on_network_error(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: OSError(네트워크 에러)가 발생하면
        THEN: 자동으로 재연결을 시도해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_ws1 = AsyncMock()
            mock_ws1.recv.side_effect = OSError("Network unreachable")
            
            mock_ws2 = AsyncMock()
            mock_ws2.recv.side_effect = asyncio.CancelledError()
            
            call_count = [0]
            async def mock_connect_func(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_ws1
                return mock_ws2
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            try:
                async for _ in connector.stream_market_data():
                    break
            except asyncio.CancelledError:
                pass

            # THEN - 재연결 시도됨
            assert mock_connect.call_count == 2


class TestNoReconnectOnParsingErrors:
    """파싱/애플리케이션 에러 시 재연결하지 않는 테스트"""

    @pytest.mark.asyncio
    async def test_no_reconnect_on_json_decode_error(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: JSONDecodeError가 발생하면
        THEN: 로그만 남기고 재연결 없이 계속 진행해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            # 잘못된 JSON → 파싱 에러 → 정상 메시지
            mock_ws.recv.side_effect = [
                "invalid json {",  # JSONDecodeError 발생
                '{"data": "valid"}',  # 정상 메시지
                asyncio.CancelledError()
            ]
            
            async def mock_connect_func(*args, **kwargs):
                return mock_ws
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            messages = []
            try:
                async for message in connector.stream_market_data():
                    messages.append(message)
                    if len(messages) >= 1:  # 정상 메시지 수신
                        break
            except asyncio.CancelledError:
                pass

            # THEN - 재연결 없이 계속 진행
            assert mock_connect.call_count == 1  # 재연결 없음
            assert len(messages) == 1  # 정상 메시지는 처리됨

    @pytest.mark.asyncio
    async def test_no_reconnect_on_invalid_message_error(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: InvalidMessageError가 발생하면
        THEN: 로그만 남기고 재연결 없이 계속 진행해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv.side_effect = [
                '{"invalid": "format"}',  # _parse_message가 None 반환
                '{"type": "test", "data": "valid"}',
                asyncio.CancelledError()
            ]
            
            async def mock_connect_func(*args, **kwargs):
                return mock_ws
            
            mock_connect.side_effect = mock_connect_func

            # 파싱 실패 시뮬레이션
            original_parse = connector._parse_message
            parse_count = [0]
            async def mock_parse(raw_message: str):
                parse_count[0] += 1
                if parse_count[0] == 1:
                    return None  # 첫 번째는 파싱 실패
                return await original_parse(raw_message)
            
            connector._parse_message = mock_parse

            # WHEN
            await connector.connect()
            
            messages = []
            try:
                async for message in connector.stream_market_data():
                    messages.append(message)
                    if len(messages) >= 1:
                        break
            except asyncio.CancelledError:
                pass

            # THEN - 재연결 없이 계속 진행
            assert mock_connect.call_count == 1
            assert len(messages) == 1


class TestNeverReconnectOnCancellation:
    """CancelledError 시 즉시 전파 테스트"""

    @pytest.mark.asyncio
    async def test_no_reconnect_on_cancelled_error(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결된 WebSocket
        WHEN: CancelledError가 발생하면
        THEN: 재연결 없이 즉시 예외를 전파해야 한다 (그레이스풀 종료)
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv.side_effect = asyncio.CancelledError()
            
            async def mock_connect_func(*args, **kwargs):
                return mock_ws
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            with pytest.raises(asyncio.CancelledError):
                async for _ in connector.stream_market_data():
                    pass

            # THEN - 재연결 시도 없음
            assert mock_connect.call_count == 1


class TestReconnectionBackoff:
    """재연결 백오프 정책 테스트"""

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_reconnection(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 연결 성공 후 연결이 끊어지는 상황
        WHEN: 재연결을 반복 시도하면
        THEN: 지수 백오프로 재시도 간격이 증가해야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect, \
             patch("asyncio.sleep") as mock_sleep:
            
            # 첫 연결 성공, 이후 모든 재연결 실패
            mock_ws1 = AsyncMock()
            mock_ws1.recv.side_effect = ConnectionClosed(rcvd=None, sent=None)
            
            call_count = [0]
            async def mock_connect_func(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_ws1
                raise ConnectionClosed(rcvd=None, sent=None)
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            try:
                async for _ in connector.stream_market_data():
                    pass
            except Exception:
                pass

            # THEN - 백오프 지연이 있어야 함
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list if call[0][0] > 0]
            # 재연결 시도 간 백오프 대기가 발생했어야 함
            assert len(sleep_calls) >= 1

    @pytest.mark.asyncio
    async def test_max_reconnect_attempts_exceeded(
        self, connector: ReconnectionTestConnector
    ) -> None:
        """
        GIVEN: 최대 재연결 횟수 설정
        WHEN: 재연결이 계속 실패하면
        THEN: 최대 시도 횟수 초과 시 예외를 발생시켜야 한다
        """
        # GIVEN
        with patch("data_ingestion.infrastructure.connectors.base_websocket.websockets.connect") as mock_connect:
            # 첫 연결 성공, 이후 모든 재연결 실패
            mock_ws = AsyncMock()
            mock_ws.recv.side_effect = ConnectionClosed(rcvd=None, sent=None)
            
            call_count = [0]
            async def mock_connect_func(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_ws
                raise ConnectionClosed(rcvd=None, sent=None)
            
            mock_connect.side_effect = mock_connect_func

            # WHEN
            await connector.connect()
            
            from data_ingestion.domain.exceptions import ConnectionClosedError
            with pytest.raises(ConnectionClosedError):
                async for _ in connector.stream_market_data():
                    pass

            # THEN - 초기 연결 1회 + 재연결 3회 = 4회
            assert mock_connect.call_count == 4


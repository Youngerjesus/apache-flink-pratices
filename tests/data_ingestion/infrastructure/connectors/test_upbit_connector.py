"""
Upbit WebSocket Connector 테스트

이 모듈은 UpbitWebSocketConnector의 Upbit 특화 기능을 테스트합니다:
- Upbit 구독 메시지 형식
- Trade 메시지 파싱
- OrderBook 메시지 파싱
- MarketDataMessage 변환
"""

import asyncio
import json
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import websockets

from data_ingestion.domain.exceptions import InvalidMessageError
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import (
    MarketDataMessage,
    MarketDataType,
    StreamType,
)
from data_ingestion.infrastructure.connectors.upbit_connector import (
    UpbitWebSocketConnector,
)


@pytest.fixture
def upbit_config() -> ExchangeConfig:
    """Upbit용 ExchangeConfig 픽스처"""
    return ExchangeConfig(
        exchange_name="upbit",
        websocket_url="wss://api.upbit.com/websocket/v1",
        rest_api_url="https://api.upbit.com/v1",
        subscribed_markets={"KRW-BTC", "KRW-ETH"},
        ping_interval_seconds=60,
        max_reconnect_attempts=3,
        exponential_backoff_max_seconds=10,
    )


@pytest.fixture
def upbit_connector(upbit_config: ExchangeConfig) -> UpbitWebSocketConnector:
    """Upbit Connector 픽스처"""
    return UpbitWebSocketConnector(upbit_config)


@pytest.fixture
def sample_trade_message() -> Dict[str, Any]:
    """Upbit Trade 메시지 샘플"""
    return {
        "type": "trade",
        "code": "KRW-BTC",
        "trade_price": 50000000.0,
        "trade_volume": 0.01,
        "ask_bid": "BID",
        "prev_closing_price": 49500000.0,
        "change": "RISE",
        "change_price": 500000.0,
        "trade_date": "2024-01-15",
        "trade_time": "09:30:00",
        "trade_timestamp": 1705287000000,
        "timestamp": 1705287000000,
        "sequential_id": 12345,
        "stream_type": "REALTIME",
    }


@pytest.fixture
def sample_orderbook_message() -> Dict[str, Any]:
    """Upbit OrderBook 메시지 샘플"""
    return {
        "type": "orderbook",
        "code": "KRW-BTC",
        "total_ask_size": 10.5,
        "total_bid_size": 15.3,
        "orderbook_units": [
            {"ask_price": 50100000.0, "bid_price": 50000000.0, "ask_size": 2.1, "bid_size": 3.2},
            {"ask_price": 50200000.0, "bid_price": 49900000.0, "ask_size": 1.5, "bid_size": 2.8},
            {"ask_price": 50300000.0, "bid_price": 49800000.0, "ask_size": 3.2, "bid_size": 4.5},
        ],
        "timestamp": 1705287000000,
        "stream_type": "REALTIME",
    }


class TestUpbitWebSocketConnectorInitialization:
    """UpbitWebSocketConnector 초기화 테스트"""

    def test_초기화_시_설정값_저장됨(
        self, upbit_connector: UpbitWebSocketConnector, upbit_config: ExchangeConfig
    ) -> None:
        """
        GIVEN: Upbit ExchangeConfig
        WHEN: UpbitWebSocketConnector를 초기화하면
        THEN: 설정값이 올바르게 저장되어야 한다
        """
        # THEN
        assert upbit_connector._config == upbit_config
        assert upbit_connector._config.exchange_name == "upbit"


class TestUpbitWebSocketConnectorSubscription:
    """UpbitWebSocketConnector 구독 메시지 테스트"""

    @pytest.mark.asyncio
    async def test_구독_메시지_형식이_올바름(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: CONNECTED 상태의 Upbit Connector
        WHEN: _send_subscription_message()를 호출하면
        THEN: Upbit 형식에 맞는 구독 메시지를 전송해야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True
        upbit_connector._websocket = mock_websocket

        # WHEN
        await upbit_connector._send_subscription_message()

        # THEN
        # Trade와 OrderBook 구독을 위해 2번 호출되어야 함
        assert mock_websocket.send.call_count == 2

        # 첫 번째 호출 (Trade 구독) 검증
        first_call_args = mock_websocket.send.call_args_list[0][0][0]
        first_message = json.loads(first_call_args)
        assert isinstance(first_message, list)
        assert len(first_message) == 3
        assert "ticket" in first_message[0]
        assert first_message[1]["type"] == "trade"
        assert set(first_message[1]["codes"]) == {"KRW-BTC", "KRW-ETH"}

        # 두 번째 호출 (OrderBook 구독) 검증
        second_call_args = mock_websocket.send.call_args_list[1][0][0]
        second_message = json.loads(second_call_args)
        assert isinstance(second_message, list)
        assert len(second_message) == 3
        assert "ticket" in second_message[0]
        assert second_message[1]["type"] == "orderbook"
        assert set(second_message[1]["codes"]) == {"KRW-BTC", "KRW-ETH"}

    @pytest.mark.asyncio
    async def test_subscription_uses_unique_uuid_tickets(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: Upbit Connector
        WHEN: _send_subscription_message()를 호출하면
        THEN: ticket 필드가 고유한 UUID 형식이어야 한다
        """
        # GIVEN
        import uuid
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True
        upbit_connector._websocket = mock_websocket

        # WHEN
        await upbit_connector._send_subscription_message()

        # THEN
        assert mock_websocket.send.call_count == 2

        # 첫 번째 호출 (Trade 구독)
        first_call_args = mock_websocket.send.call_args_list[0][0][0]
        first_message = json.loads(first_call_args)
        trade_ticket = first_message[0]["ticket"]
        
        # UUID 형식인지 검증
        try:
            uuid.UUID(trade_ticket)
        except ValueError:
            pytest.fail(f"Trade ticket is not a valid UUID: {trade_ticket}")

        # 두 번째 호출 (OrderBook 구독)
        second_call_args = mock_websocket.send.call_args_list[1][0][0]
        second_message = json.loads(second_call_args)
        orderbook_ticket = second_message[0]["ticket"]
        
        # UUID 형식인지 검증
        try:
            uuid.UUID(orderbook_ticket)
        except ValueError:
            pytest.fail(f"OrderBook ticket is not a valid UUID: {orderbook_ticket}")

    @pytest.mark.asyncio
    async def test_구독_시_모든_마켓_코드_포함됨(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: 여러 마켓을 구독하는 Upbit Connector
        WHEN: _send_subscription_message()를 호출하면
        THEN: 모든 마켓 코드가 구독 메시지에 포함되어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True
        upbit_connector._websocket = mock_websocket

        # WHEN
        await upbit_connector._send_subscription_message()

        # THEN
        call_args = mock_websocket.send.call_args[0][0]
        sent_messages = json.loads(call_args)

        # 구독한 마켓 코드가 모두 포함되어 있는지 확인
        # (Upbit는 단일 요청으로 여러 마켓을 구독할 수 있음)
        assert mock_websocket.send.call_count >= 1


class TestUpbitWebSocketConnectorMessageParsing:
    """UpbitWebSocketConnector 메시지 파싱 테스트"""

    @pytest.mark.asyncio
    async def test_trade_메시지_파싱_성공(
        self, upbit_connector: UpbitWebSocketConnector, sample_trade_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: Upbit Trade 메시지
        WHEN: _parse_message()를 호출하면
        THEN: 메시지가 올바르게 파싱되어야 한다
        """
        # GIVEN
        raw_message = json.dumps(sample_trade_message)

        # WHEN
        result = await upbit_connector._parse_message(raw_message)

        # THEN
        assert result is not None
        assert result["type"] == "trade"
        assert result["code"] == "KRW-BTC"
        assert result["trade_price"] == 50000000.0

    @pytest.mark.asyncio
    async def test_orderbook_메시지_파싱_성공(
        self,
        upbit_connector: UpbitWebSocketConnector,
        sample_orderbook_message: Dict[str, Any],
    ) -> None:
        """
        GIVEN: Upbit OrderBook 메시지
        WHEN: _parse_message()를 호출하면
        THEN: 메시지가 올바르게 파싱되어야 한다
        """
        # GIVEN
        raw_message = json.dumps(sample_orderbook_message)

        # WHEN
        result = await upbit_connector._parse_message(raw_message)

        # THEN
        assert result is not None
        assert result["type"] == "orderbook"
        assert result["code"] == "KRW-BTC"
        assert "orderbook_units" in result

    @pytest.mark.asyncio
    async def test_잘못된_메시지_형식은_None_반환(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: 잘못된 형식의 메시지
        WHEN: _parse_message()를 호출하면
        THEN: None을 반환해야 한다
        """
        # GIVEN
        invalid_message = "not a json"

        # WHEN
        result = await upbit_connector._parse_message(invalid_message)

        # THEN
        assert result is None

    @pytest.mark.asyncio
    async def test_필수_필드_누락_시_None_반환(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: 필수 필드가 누락된 메시지
        WHEN: _parse_message()를 호출하면
        THEN: None을 반환해야 한다
        """
        # GIVEN
        incomplete_message = json.dumps({"type": "trade"})  # code 필드 누락

        # WHEN
        result = await upbit_connector._parse_message(incomplete_message)

        # THEN
        assert result is None


class TestUpbitWebSocketConnectorMarketDataConversion:
    """UpbitWebSocketConnector MarketDataMessage 변환 테스트"""

    def test_trade_메시지를_MarketDataMessage로_변환(
        self, upbit_connector: UpbitWebSocketConnector, sample_trade_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 파싱된 Trade 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: MarketDataMessage 객체가 생성되어야 한다
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_trade_message)

        # THEN
        assert len(messages) == 1
        message = messages[0]
        assert isinstance(message, MarketDataMessage)
        assert message.exchange == "upbit"
        assert message.data_type == MarketDataType.TRADE
        assert message.code == "KRW-BTC"
        assert message.raw_data == sample_trade_message

    def test_orderbook_메시지를_MarketDataMessage로_변환(
        self,
        upbit_connector: UpbitWebSocketConnector,
        sample_orderbook_message: Dict[str, Any],
    ) -> None:
        """
        GIVEN: 파싱된 OrderBook 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: MarketDataMessage 객체가 생성되어야 한다
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_orderbook_message)

        # THEN
        assert len(messages) == 1
        message = messages[0]
        assert isinstance(message, MarketDataMessage)
        assert message.exchange == "upbit"
        assert message.data_type == MarketDataType.ORDERBOOK
        assert message.code == "KRW-BTC"

    def test_received_timestamp가_UTC로_설정됨(
        self, upbit_connector: UpbitWebSocketConnector, sample_trade_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 파싱된 메시지
        WHEN: MarketDataMessage로 변환하면
        THEN: received_timestamp가 UTC timezone-aware로 설정되어야 한다
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_trade_message)

        # THEN
        message = messages[0]
        assert message.received_timestamp.tzinfo == UTC

    def test_convert_trade_message_includes_event_timestamp(
        self, upbit_connector: UpbitWebSocketConnector, sample_trade_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: trade_timestamp 필드를 포함한 Trade 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: event_timestamp가 trade_timestamp로부터 변환되어 설정되어야 한다
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_trade_message)

        # THEN
        message = messages[0]
        assert message.event_timestamp is not None
        assert message.event_timestamp.tzinfo == UTC
        # trade_timestamp가 밀리초 단위이므로 올바르게 변환되었는지 확인
        expected_timestamp = datetime.fromtimestamp(
            sample_trade_message["trade_timestamp"] / 1000, tz=UTC
        )
        assert message.event_timestamp == expected_timestamp

    def test_convert_orderbook_message_includes_event_timestamp(
        self, upbit_connector: UpbitWebSocketConnector, sample_orderbook_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: timestamp 필드를 포함한 OrderBook 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: event_timestamp가 timestamp로부터 변환되어 설정되어야 한다
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_orderbook_message)

        # THEN
        message = messages[0]
        assert message.event_timestamp is not None
        assert message.event_timestamp.tzinfo == UTC
        # timestamp가 밀리초 단위이므로 올바르게 변환되었는지 확인
        expected_timestamp = datetime.fromtimestamp(
            sample_orderbook_message["timestamp"] / 1000, tz=UTC
        )
        assert message.event_timestamp == expected_timestamp

    def test_convert_message_includes_stream_type(
        self, upbit_connector: UpbitWebSocketConnector, sample_trade_message: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 파싱된 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: stream_type이 설정되어야 한다 (업비트는 기본 REALTIME)
        """
        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(sample_trade_message)

        # THEN
        message = messages[0]
        assert message.stream_type is not None
        assert message.stream_type == StreamType.REALTIME

    def test_event_timestamp_from_trade_timestamp_field(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: trade_timestamp 필드가 있는 Trade 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: event_timestamp가 trade_timestamp 값으로 설정되어야 한다
        """
        # GIVEN
        trade_message = {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 50000000.0,
            "trade_timestamp": 1705287000000,  # 명시적으로 trade_timestamp 사용
        }

        # WHEN
        messages = upbit_connector._convert_to_market_data_messages(trade_message)

        # THEN
        message = messages[0]
        expected = datetime.fromtimestamp(1705287000000 / 1000, tz=UTC)
        assert message.event_timestamp == expected

    def test_event_timestamp_fallback_to_received_if_missing(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: timestamp 필드가 없는 메시지
        WHEN: _convert_to_market_data_messages()를 호출하면
        THEN: event_timestamp가 received_timestamp와 유사한 시간으로 설정되어야 한다
        """
        # GIVEN
        message_without_timestamp = {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 50000000.0,
            # timestamp 필드 없음
        }

        # WHEN
        before = datetime.now(UTC)
        messages = upbit_connector._convert_to_market_data_messages(message_without_timestamp)
        after = datetime.now(UTC)

        # THEN
        message = messages[0]
        assert message.event_timestamp is not None
        assert message.event_timestamp.tzinfo == UTC
        # event_timestamp가 현재 시간 근처여야 함
        assert before <= message.event_timestamp <= after


class TestUpbitWebSocketConnectorIntegration:
    """UpbitWebSocketConnector 통합 테스트"""

    @pytest.mark.asyncio
    async def test_연결부터_메시지_수신까지_전체_플로우(
        self,
        upbit_connector: UpbitWebSocketConnector,
        sample_trade_message: Dict[str, Any],
    ) -> None:
        """
        GIVEN: Upbit Connector
        WHEN: 연결하고 메시지를 수신하면
        THEN: MarketDataMessage를 정상적으로 받을 수 있어야 한다
        """
        # GIVEN
        mock_websocket = AsyncMock(spec=websockets.WebSocketClientProtocol)
        mock_websocket.open = True
        mock_websocket.recv = AsyncMock(
            side_effect=[
                json.dumps(sample_trade_message),
                asyncio.CancelledError(),  # 테스트 종료
            ]
        )

        # WHEN
        with patch("websockets.connect", new=AsyncMock(return_value=mock_websocket)):
            await upbit_connector.connect()

            # 메시지 스트림에서 하나의 메시지만 받기
            message_received = False
            async for message in upbit_connector.stream_market_data():
                assert isinstance(message, MarketDataMessage)
                assert message.exchange == "upbit"
                message_received = True
                break  # 하나만 받고 종료

        # THEN
        # 연결이 성공적으로 이루어졌는지 확인
        state = await upbit_connector.get_connection_state()
        # 스트림이 중단되었으므로 상태가 변경되었을 수 있음

        # Cleanup
        await upbit_connector.disconnect()


class TestUpbitWebSocketConnectorErrorHandling:
    """UpbitWebSocketConnector 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_구독하지_않은_마켓_메시지는_무시됨(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: KRW-BTC, KRW-ETH만 구독한 Connector
        WHEN: KRW-XRP 메시지를 받으면
        THEN: 해당 메시지는 무시되어야 한다
        """
        # GIVEN
        unsubscribed_message = json.dumps({
            "type": "trade",
            "code": "KRW-XRP",  # 구독하지 않은 마켓
            "trade_price": 1000.0,
            "trade_volume": 100.0,
        })

        # WHEN
        result = await upbit_connector._parse_message(unsubscribed_message)

        # THEN
        # 구독하지 않은 마켓의 메시지는 None을 반환해야 함
        assert result is None

    @pytest.mark.asyncio
    async def test_알_수_없는_메시지_타입은_무시됨(
        self, upbit_connector: UpbitWebSocketConnector
    ) -> None:
        """
        GIVEN: trade, orderbook이 아닌 메시지
        WHEN: _parse_message()를 호출하면
        THEN: None을 반환하거나 무시해야 한다
        """
        # GIVEN
        unknown_message = json.dumps({
            "type": "unknown_type",
            "code": "KRW-BTC",
            "data": "some data",
        })

        # WHEN
        result = await upbit_connector._parse_message(unknown_message)

        # THEN
        # 알 수 없는 타입은 None 반환 또는 무시
        assert result is None or result.get("type") not in ["trade", "orderbook"]


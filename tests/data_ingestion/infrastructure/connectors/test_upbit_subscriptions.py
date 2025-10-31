"""
UpbitWebSocketConnector 구독 상태 추적(Local) 테스트

검증 항목:
- 초기 connect 시 trade/orderbook 구독이 등록되고 ticket가 생성됨
- 메시지 수신 시 해당 구독이 ACTIVE로 전이되고 last_message_at 설정됨
- 재연결 시 기존 ticket을 재사용하여 재구독됨(새 ticket 생성 금지)
- subscribe()로 추가 구독이 가능하며 전송됨
- 조회 API(list/get)가 올바른 상태를 반환
"""

import asyncio
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
import websockets

from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.infrastructure.connectors.upbit_connector import (
    UpbitWebSocketConnector,
)


@pytest.fixture
def upbit_config() -> ExchangeConfig:
    return ExchangeConfig(
        exchange_name="upbit",
        websocket_url="wss://api.upbit.com/websocket/v1",
        rest_api_url="https://api.upbit.com/v1",
        subscribed_markets={"KRW-BTC", "KRW-ETH"},
        ping_interval_seconds=60,
        max_reconnect_attempts=2,
        exponential_backoff_max_seconds=5,
    )


@pytest.fixture
def upbit_connector(upbit_config: ExchangeConfig) -> UpbitWebSocketConnector:
    return UpbitWebSocketConnector(upbit_config)


@pytest.mark.asyncio
async def test_initial_connect_seeds_subscriptions(
    upbit_connector: UpbitWebSocketConnector,
) -> None:
    """
    GIVEN: 구독 레지스트리가 비어있는 Upbit 커넥터
    WHEN: connect()를 호출하면
    THEN: trade/orderbook 각각 하나의 ticket이 생성되어 저장되고 전송된다
    """
    mock_ws = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws.open = True
    # recv는 사용되지 않음. 스트림 시작 전까지만 검증

    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
        await upbit_connector.connect()

    # 두 번의 구독 전송(trade/orderbook)
    assert mock_ws.send.call_count == 2

    # 로컬 조회
    subs = upbit_connector.list_subscriptions()
    assert len(subs) == 2
    types = sorted(s.sub_type for s in subs)
    assert types == ["orderbook", "trade"]
    for s in subs:
        # ticket 존재
        assert isinstance(s.ticket, str) and len(s.ticket) > 0
        # 코드 세트가 구성값과 동일
        assert set(s.codes) == {"KRW-BTC", "KRW-ETH"}


@pytest.mark.asyncio
async def test_message_activation_marks_active(
    upbit_connector: UpbitWebSocketConnector,
) -> None:
    """
    GIVEN: 초기 구독 후
    WHEN: 해당 코드/타입의 메시지가 수신되면
    THEN: 해당 구독 상태가 ACTIVE로 바뀌고 last_message_at이 설정된다
    """
    # 1) 연결 및 초기 구독 시딩
    mock_ws = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws.open = True
    # 스트림에서 한 번 메시지 내보내고 Cancel로 종료
    trade_msg: Dict[str, Any] = {
        "type": "trade",
        "code": "KRW-BTC",
        "trade_price": 1.0,
        "trade_timestamp": 1705287000000,
    }
    mock_ws.recv = AsyncMock(
        side_effect=[json.dumps(trade_msg), asyncio.CancelledError()]
    )

    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
        await upbit_connector.connect()
        # 메시지 한 개 처리
        try:
            async for _ in upbit_connector.stream_market_data():
                break
        except asyncio.CancelledError:
            pass

    # 활성화 확인
    subs = upbit_connector.list_subscriptions()
    trade_sub = next(s for s in subs if s.sub_type == "trade")
    assert trade_sub.status == "ACTIVE"
    assert trade_sub.last_message_at is not None


@pytest.mark.asyncio
async def test_reconnect_reuses_existing_tickets(
    upbit_connector: UpbitWebSocketConnector,
) -> None:
    """
    GIVEN: 최초 연결로 시딩된 trade/orderbook 구독
    WHEN: disconnect 후 재연결
    THEN: 동일한 ticket으로 재전송되며 새 ticket이 생성되지 않는다
    """
    # 최초 연결
    mock_ws1 = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws1.open = True
    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws1)):
        await upbit_connector.connect()
    # 저장된 ticket 스냅샷
    initial = {s.sub_type: s.ticket for s in upbit_connector.list_subscriptions()}
    assert mock_ws1.send.call_count == 2

    # 재연결: 새 소켓
    mock_ws2 = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws2.open = True
    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws2)):
        await upbit_connector.disconnect()
        await upbit_connector.connect()

    # 재전송 2회 (기존 두 구독)
    assert mock_ws2.send.call_count == 2

    # 재연결 후에도 ticket 동일
    after = {s.sub_type: s.ticket for s in upbit_connector.list_subscriptions()}
    assert after == initial


@pytest.mark.asyncio
async def test_subscribe_adds_new_subscription_and_sends(
    upbit_connector: UpbitWebSocketConnector,
) -> None:
    """
    GIVEN: 연결된 상태
    WHEN: subscribe('trade', ['KRW-XRP']) 호출
    THEN: 새 ticket 생성/저장 및 전송 1회
    """
    mock_ws = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws.open = True
    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
        await upbit_connector.connect()

    mock_ws.send.reset_mock()

    ticket = await upbit_connector.subscribe("trade", ["KRW-XRP"])
    assert isinstance(ticket, str) and len(ticket) > 0

    # 전송 1회
    assert mock_ws.send.call_count == 1

    # 레지스트리에 포함
    sub = upbit_connector.get_subscription(ticket)
    assert sub is not None
    assert sub.sub_type == "trade"
    assert set(sub.codes) == {"KRW-XRP"}


@pytest.mark.asyncio
async def test_query_apis_return_correct_state(
    upbit_connector: UpbitWebSocketConnector,
) -> None:
    """
    GIVEN: 초기 연결로 두 구독이 등록된 상태
    WHEN: list/get API를 호출하면
    THEN: 저장된 상태가 그대로 반환되어야 한다
    """
    mock_ws = AsyncMock(spec=websockets.WebSocketClientProtocol)
    mock_ws.open = True
    with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
        await upbit_connector.connect()

    subs = upbit_connector.list_subscriptions()
    assert len(subs) == 2
    for s in subs:
        got = upbit_connector.get_subscription(s.ticket)
        assert got is not None
        assert got.ticket == s.ticket
        assert got.sub_type in ("trade", "orderbook")
        assert set(got.codes) == {"KRW-BTC", "KRW-ETH"}



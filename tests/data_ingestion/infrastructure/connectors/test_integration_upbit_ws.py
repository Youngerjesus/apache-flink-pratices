"""
실 WS 통합 테스트 (네트워크 필요)

환경 변수 ALLOW_NETWORK=1 일 때만 실행됩니다.
정상 흐름을 검증하고, 재연결/타임아웃 시나리오는 제어 가능한 서버가 없어 스킵합니다.
"""

import asyncio
import os
from datetime import UTC, datetime

import pytest

from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.infrastructure.connectors.upbit_connector import (
    UpbitWebSocketConnector,
)


requires_network = pytest.mark.skipif(
    os.environ.get("ALLOW_NETWORK") != "1",
    reason="Network tests are disabled. Set ALLOW_NETWORK=1 to enable.",
)


@requires_network
@pytest.mark.asyncio
async def test_upbit_real_ws_connect_and_receive_one_message() -> None:
    config = ExchangeConfig(
        exchange_name="upbit",
        websocket_url="wss://api.upbit.com/websocket/v1",
        rest_api_url="https://api.upbit.com/v1",
        subscribed_markets={"KRW-BTC"},
        ping_interval_seconds=60,
        max_reconnect_attempts=3,
        exponential_backoff_max_seconds=10,
    )

    connector = UpbitWebSocketConnector(config)
    await connector.connect()

    received = []

    async def consume():
        async for msg in connector.stream_market_data():
            received.append(msg)
            if len(received) >= 1:
                break

    try:
        await asyncio.wait_for(consume(), timeout=10)
    finally:
        await connector.disconnect()

    assert len(received) >= 1


@requires_network
@pytest.mark.skip(reason="재연결/타임아웃 강제는 외부 서버 제어가 어려워 스킵")
@pytest.mark.asyncio
async def test_upbit_real_ws_reconnect_scenario_skipped() -> None:  # pragma: no cover
    pass


@requires_network
@pytest.mark.skip(reason="재연결/타임아웃 강제는 외부 서버 제어가 어려워 스킵")
@pytest.mark.asyncio
async def test_upbit_real_ws_timeout_scenario_skipped() -> None:  # pragma: no cover
    pass



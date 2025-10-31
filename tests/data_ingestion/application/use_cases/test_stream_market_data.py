"""
stream_market_data 유즈케이스 테스트

실시간 마켓 데이터 스트리밍 유즈케이스의 핵심 기능을 테스트합니다:
- 입력 검증
- 설정 생성
- 의존성 생성 및 서비스 시작
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_ingestion.domain.exceptions import ValidationException


# stream_market_data를 import하지만, 아직 구현되지 않았으므로 테스트 실행 시 import error 발생 가능
try:
    from data_ingestion.application.use_cases.stream_market_data import stream_market_data
except ImportError:
    stream_market_data = None


@pytest.fixture
def valid_subscribed_markets() -> set[str]:
    """유효한 구독 마켓 픽스처"""
    return {"KRW-BTC", "KRW-ETH"}


@pytest.fixture
def kafka_config() -> Dict[str, Any]:
    """Kafka 설정 픽스처"""
    return {
        "bootstrap.servers": "localhost:9092",
        "client.id": "test-producer",
    }


@pytest.mark.skipif(stream_market_data is None, reason="stream_market_data not implemented yet")
class TestStreamMarketDataValidation:
    """stream_market_data 유즈케이스 입력 검증 테스트"""

    @pytest.mark.asyncio
    async def test_빈_subscribed_markets_시_ValidationException(
        self, kafka_config: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 빈 subscribed_markets
        WHEN: stream_market_data()를 호출하면
        THEN: ValidationException이 발생해야 한다
        """
        # GIVEN
        empty_markets = set()

        # WHEN, THEN
        with pytest.raises(ValidationException, match="cannot be empty"):
            await stream_market_data(empty_markets, kafka_config)

    @pytest.mark.asyncio
    async def test_잘못된_마켓_코드_형식_시_예외(
        self, kafka_config: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 잘못된 형식의 마켓 코드 (예: "BTC-KRW")
        WHEN: stream_market_data()를 호출하면
        THEN: ValidationException이 발생해야 한다
        """
        # GIVEN
        invalid_markets = {"BTC-KRW"}  # 역순

        # WHEN, THEN
        with pytest.raises(ValidationException, match="Invalid market code"):
            await stream_market_data(invalid_markets, kafka_config)

    @pytest.mark.asyncio
    async def test_혼합된_마켓_코드_중_일부_잘못됨(
        self, kafka_config: Dict[str, Any]
    ) -> None:
        """
        GIVEN: 일부는 유효하고 일부는 잘못된 마켓 코드
        WHEN: stream_market_data()를 호출하면
        THEN: ValidationException이 발생해야 한다
        """
        # GIVEN
        mixed_markets = {"KRW-BTC", "BTC-KRW"}  # 두 번째가 잘못됨

        # WHEN, THEN
        with pytest.raises(ValidationException, match="Invalid market code"):
            await stream_market_data(mixed_markets, kafka_config)


@pytest.mark.skipif(stream_market_data is None, reason="stream_market_data not implemented yet")
class TestStreamMarketDataIntegration:
    """stream_market_data 유즈케이스 통합 테스트"""

    @pytest.mark.asyncio
    @patch("data_ingestion.application.use_cases.stream_market_data.IngestionService")
    @patch("data_ingestion.application.use_cases.stream_market_data.KafkaProducerAdapter")
    @patch("data_ingestion.application.use_cases.stream_market_data.UpbitWebSocketConnector")
    @patch("data_ingestion.application.use_cases.stream_market_data.create_upbit_config")
    async def test_유효한_마켓으로_스트리밍_시작(
        self,
        mock_create_config: MagicMock,
        mock_connector_class: MagicMock,
        mock_publisher_class: MagicMock,
        mock_service_class: MagicMock,
        valid_subscribed_markets: set[str],
        kafka_config: Dict[str, Any],
    ) -> None:
        """
        GIVEN: 유효한 마켓 코드와 Kafka 설정
        WHEN: stream_market_data()를 호출하면
        THEN: 올바른 순서로 의존성이 생성되고 서비스가 시작되어야 한다
        """
        # GIVEN
        mock_config = MagicMock()
        mock_create_config.return_value = mock_config

        mock_connector = AsyncMock()
        mock_connector_class.return_value = mock_connector

        mock_publisher = AsyncMock()
        mock_publisher_class.return_value = mock_publisher

        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        # WHEN
        # stream_market_data는 무한 루프이므로 Task를 시작하고 바로 취소
        task = asyncio.create_task(
            stream_market_data(valid_subscribed_markets, kafka_config)
        )
        await asyncio.sleep(0.2)  # 초기화 대기
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # THEN
        # 1. config 생성 확인
        mock_create_config.assert_called_once_with(valid_subscribed_markets)

        # 2. connector 생성 확인
        mock_connector_class.assert_called_once_with(mock_config)

        # 3. publisher 생성 확인
        mock_publisher_class.assert_called_once_with(kafka_config)

        # 4. service 생성 확인
        mock_service_class.assert_called_once_with(mock_connector, mock_publisher)

        # 5. service 시작 확인
        mock_service.start.assert_called_once()


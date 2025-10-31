"""
실시간 마켓 데이터 스트리밍 유즈케이스

거래소로부터 실시간 마켓 데이터를 수집하여 Kafka로 발행하는 전체 파이프라인을 관리합니다.
"""

import asyncio
import logging
from typing import Any

from data_ingestion.application.services.ingestion_service import IngestionService
from data_ingestion.domain.exceptions import ValidationException
from data_ingestion.infrastructure.connectors.upbit_config import create_upbit_config
from data_ingestion.infrastructure.connectors.upbit_connector import UpbitWebSocketConnector
from data_ingestion.infrastructure.kafka.kafka_producer import KafkaProducerAdapter

logger = logging.getLogger(__name__)


async def stream_market_data(
    subscribed_markets: set[str],
    kafka_config: dict[str, Any]
) -> None:
    """
    실시간 마켓 데이터 스트리밍 유즈케이스

    거래소로부터 실시간 마켓 데이터를 수집하여 Kafka로 발행합니다.
    이 함수는 무한 실행되며, 외부에서 중단될 때까지 계속 실행됩니다.

    Args:
        subscribed_markets: 구독할 마켓 코드 집합 (예: {"KRW-BTC", "KRW-ETH"})
        kafka_config: Kafka Producer 설정 딕셔너리

    Raises:
        ValidationException: subscribed_markets가 비어있거나 잘못된 형식인 경우
        ConnectionFailedError: 거래소 연결 실패 시
        PublishException: Kafka 발행 실패가 연속 10회 발생한 경우

    Examples:
        >>> kafka_config = {"bootstrap.servers": "localhost:9092"}
        >>> await stream_market_data({"KRW-BTC"}, kafka_config)
    """
    # 1. 입력 검증
    if not subscribed_markets:
        raise ValidationException("subscribed_markets cannot be empty")

    for code in subscribed_markets:
        if not code.startswith("KRW-"):
            raise ValidationException(f"Invalid market code: {code}. Must start with 'KRW-'")

    logger.info(f"Starting market data streaming for {len(subscribed_markets)} markets")

    # 2. 설정 생성 (upbit_config 사용)
    exchange_config = create_upbit_config(subscribed_markets)

    # 3. 의존성 생성
    connector = UpbitWebSocketConnector(exchange_config)
    publisher = KafkaProducerAdapter(kafka_config)

    # 4. 서비스 생성 및 시작
    service = IngestionService(connector, publisher)

    try:
        await service.start()
        logger.info("Market data streaming started successfully")

        # 무한 실행 (외부에서 중단될 때까지)
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected, stopping service...")
    except Exception as e:
        logger.error(f"Unexpected error in market data streaming: {e}")
        raise
    finally:
        logger.info("Stopping market data streaming...")
        await service.stop()
        logger.info("Market data streaming stopped")


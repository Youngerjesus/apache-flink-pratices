"""
데이터 수집 오케스트레이션 서비스

ExchangeConnector와 MessagePublisher를 조합하여 실시간 데이터 수집 파이프라인을 관리합니다.
"""

import asyncio
import logging
from datetime import datetime, UTC
from typing import Optional

from google.protobuf.timestamp_pb2 import Timestamp

from data_ingestion.domain.exceptions import PublishException
from data_ingestion.domain.models.market_data import MarketDataMessage, MarketDataType
from data_ingestion.domain.ports.exchange_connector import ExchangeConnector
from data_ingestion.domain.ports.message_publisher import MessagePublisher
from data_ingestion.infrastructure.proto_generated import common_pb2, market_data_pb2

logger = logging.getLogger(__name__)


class IngestionService:
    """
    데이터 수집 오케스트레이션 서비스

    ExchangeConnector로부터 시장 데이터를 수신하고,
    Protobuf로 직렬화하여 MessagePublisher를 통해 Kafka에 발행합니다.

    Features:
        - 비동기 데이터 스트리밍
        - Graceful shutdown
        - 자동 에러 복구 (일시적 실패)
        - 연속 실패 시 서비스 중단

    Attributes:
        _connector: 거래소 데이터 소스
        _publisher: 메시지 발행 대상
        _max_consecutive_failures: 연속 실패 허용 횟수
        _running: 서비스 실행 상태
        _lock: 동시성 제어용 락
        _processed_count: 처리된 메시지 수
        _consecutive_failures: 연속 실패 횟수
        _background_task: 백그라운드 태스크 참조
    """

    def __init__(
        self,
        connector: ExchangeConnector,
        publisher: MessagePublisher,
        max_consecutive_failures: int = 10,
    ):
        """
        IngestionService 초기화

        Args:
            connector: 거래소 데이터 소스
            publisher: 메시지 발행 대상
            max_consecutive_failures: 연속 실패 허용 횟수 (기본값: 10)
        """
        self._connector = connector
        self._publisher = publisher
        self._max_consecutive_failures = max_consecutive_failures

        self._running = False
        self._lock = asyncio.Lock()
        self._processed_count = 0
        self._consecutive_failures = 0
        self._background_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        서비스 시작

        1. ExchangeConnector 연결
        2. 백그라운드에서 데이터 수신 및 발행 시작

        Raises:
            RuntimeError: 이미 실행 중인 경우
            ConnectionFailedError: 연결 실패 시
        """
        async with self._lock:
            if self._running:
                raise RuntimeError("Service is already running")

            logger.info("Starting IngestionService...")

            # 1. Connector 연결
            await self._connector.connect()

            # 2. 백그라운드 태스크 시작
            self._running = True
            self._background_task = asyncio.create_task(self._consume_and_publish())

            logger.info("IngestionService started successfully")

    async def stop(self) -> None:
        """
        서비스 중단 (Graceful Shutdown)

        1. 백그라운드 태스크 중단 대기
        2. Publisher flush (대기 중인 메시지 전송)
        3. Connector 연결 종료

        멱등성을 보장하여 여러 번 호출해도 안전합니다.
        """
        async with self._lock:
            if not self._running:
                logger.debug("Service is not running, skipping stop")
                return

            logger.info("Stopping IngestionService...")
            self._running = False

        try:
            # 1. 백그라운드 태스크 종료 대기 (최대 5초)
            if self._background_task:
                try:
                    await asyncio.wait_for(self._background_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Background task did not finish within timeout, cancelling")
                    self._background_task.cancel()
                    try:
                        await self._background_task
                    except asyncio.CancelledError:
                        pass

            # 2. Publisher flush
            try:
                flushed = await self._publisher.flush(timeout=5.0)
                logger.info(f"Flushed {flushed} pending messages")
            except Exception as e:
                logger.error(f"Failed to flush publisher: {e}")

            # 3. Connector 연결 종료
            try:
                await self._connector.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect connector: {e}")

        finally:
            logger.info("IngestionService stopped")

    async def _consume_and_publish(self) -> None:
        """
        메시지 수신 및 발행 메인 루프

        1. Connector로부터 MarketDataMessage 수신
        2. 구독 마켓 필터링
        3. Protobuf 직렬화
        4. Publisher로 발행
        5. 에러 처리 및 로깅

        Raises:
            PublishException: 연속 10회 발행 실패 시
        """
        logger.info("Starting data consumption loop...")

        try:
            async for message in self._connector.stream_market_data():
                if not self._running:
                    logger.info("Service stopped, exiting consumption loop")
                    break

                # 1. 구독 마켓 필터링
                if not self._is_subscribed_market(message):
                    logger.debug(f"Skipping unsubscribed market: {message.code}")
                    continue

                # 2. Protobuf 변환
                try:
                    proto_message = self._convert_to_protobuf(message)
                except Exception as e:
                    logger.error(f"Failed to convert message to Protobuf: {e}")
                    continue

                # 3. Kafka 토픽 및 키 결정
                topic = self._get_topic_for_message(message)
                key = message.code.encode("utf-8")

                # 4. 발행
                try:
                    await self._publisher.publish(topic, key, proto_message)
                    self._consecutive_failures = 0  # 성공 시 카운터 리셋
                    self._processed_count += 1

                    # 1,000개마다 로그 출력
                    if self._processed_count % 1000 == 0:
                        logger.info(f"Processed {self._processed_count} messages")

                except PublishException as e:
                    self._consecutive_failures += 1
                    logger.error(
                        f"Failed to publish message (consecutive failures: {self._consecutive_failures}): {e}"
                    )

                    # 연속 10회 실패 시 서비스 중단
                    if self._consecutive_failures >= self._max_consecutive_failures:
                        logger.critical(
                            f"Consecutive publish failures reached {self._max_consecutive_failures}. "
                            "Shutting down service."
                        )
                        raise

        except Exception as e:
            logger.error(f"Error in consumption loop: {e}")
            raise
        finally:
            logger.info("Data consumption loop ended")

    def _is_subscribed_market(self, message: MarketDataMessage) -> bool:
        """
        메시지가 구독 마켓에 속하는지 확인

        Args:
            message: 검증할 메시지

        Returns:
            구독 마켓 여부
        """
        subscribed = self._connector.config.subscribed_markets
        return message.code in subscribed

    def _convert_to_protobuf(self, message: MarketDataMessage) -> market_data_pb2.Trade | market_data_pb2.OrderBookUpdate:
        """
        MarketDataMessage를 Protobuf 메시지로 변환

        Args:
            message: 변환할 메시지

        Returns:
            Protobuf Trade 또는 OrderBookUpdate 메시지

        Raises:
            ValueError: 알 수 없는 data_type인 경우
        """
        if message.data_type == MarketDataType.TRADE:
            return self._convert_to_trade_proto(message)
        elif message.data_type == MarketDataType.ORDERBOOK:
            return self._convert_to_orderbook_proto(message)
        else:
            raise ValueError(f"Unknown data_type: {message.data_type}")

    def _convert_to_trade_proto(self, message: MarketDataMessage) -> market_data_pb2.Trade:
        """Trade 메시지를 Protobuf로 변환"""
        raw = message.raw_data

        # Timestamp 변환
        trade_ts = Timestamp()
        trade_ts.FromDatetime(message.event_timestamp)
        received_ts = Timestamp()
        received_ts.FromDatetime(message.received_timestamp)

        # AskBid 변환
        ask_bid_map = {
            "ASK": common_pb2.ASK,
            "BID": common_pb2.BID,
        }
        ask_bid = ask_bid_map.get(raw.get("ask_bid", ""), common_pb2.ASK_BID_UNSPECIFIED)

        # ChangeType 변환
        change_map = {
            "RISE": common_pb2.RISE,
            "EVEN": common_pb2.EVEN,
            "FALL": common_pb2.FALL,
        }
        change = change_map.get(raw.get("change", ""), common_pb2.CHANGE_TYPE_UNSPECIFIED)

        # StreamType 변환
        stream_type = common_pb2.REALTIME if message.stream_type.value == "realtime" else common_pb2.SNAPSHOT

        return market_data_pb2.Trade(
            exchange=common_pb2.UPBIT,
            code=message.code,
            trade_price=raw.get("trade_price", 0.0),
            trade_volume=raw.get("trade_volume", 0.0),
            ask_bid=ask_bid,
            prev_closing_price=raw.get("prev_closing_price", 0.0),
            change=change,
            change_price=raw.get("change_price", 0.0),
            trade_timestamp=trade_ts,
            sequential_id=raw.get("sequential_id", 0),
            stream_type=stream_type,
            received_timestamp=received_ts,
        )

    def _convert_to_orderbook_proto(self, message: MarketDataMessage) -> market_data_pb2.OrderBookUpdate:
        """OrderBook 메시지를 Protobuf로 변환"""
        raw = message.raw_data

        # Timestamp 변환
        event_ts = Timestamp()
        event_ts.FromDatetime(message.event_timestamp)
        received_ts = Timestamp()
        received_ts.FromDatetime(message.received_timestamp)

        # OrderBookLevel 변환
        asks = [
            market_data_pb2.OrderBookLevel(price=level.get("price", 0.0), size=level.get("size", 0.0))
            for level in raw.get("asks", [])
        ]
        bids = [
            market_data_pb2.OrderBookLevel(price=level.get("price", 0.0), size=level.get("size", 0.0))
            for level in raw.get("bids", [])
        ]

        # StreamType 변환
        stream_type = common_pb2.REALTIME if message.stream_type.value == "realtime" else common_pb2.SNAPSHOT

        return market_data_pb2.OrderBookUpdate(
            exchange=common_pb2.UPBIT,
            code=message.code,
            total_ask_size=raw.get("total_ask_size", 0.0),
            total_bid_size=raw.get("total_bid_size", 0.0),
            asks=asks,
            bids=bids,
            stream_type=stream_type,
            event_timestamp=event_ts,
            received_timestamp=received_ts,
        )

    def _get_topic_for_message(self, message: MarketDataMessage) -> str:
        """
        메시지 타입에 따른 Kafka 토픽 결정

        Args:
            message: 메시지

        Returns:
            Kafka 토픽 이름
        """
        if message.data_type == MarketDataType.TRADE:
            return "upbit.trades.v1"
        elif message.data_type == MarketDataType.ORDERBOOK:
            return "upbit.orderbooks.v1"
        else:
            return "upbit.unknown.v1"

    def get_status(self) -> dict:
        """
        서비스 상태 조회

        Returns:
            상태 정보 딕셔너리:
                - running: 실행 중 여부
                - processed: 처리된 메시지 수
                - consecutive_failures: 연속 실패 횟수
        """
        return {
            "running": self._running,
            "processed": self._processed_count,
            "consecutive_failures": self._consecutive_failures,
        }


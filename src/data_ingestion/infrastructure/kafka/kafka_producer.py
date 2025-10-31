"""
Kafka Producer 구현

이 모듈은 Protobuf 메시지를 Kafka로 발행하는 기능을 제공합니다.
MessagePublisher 인터페이스를 구현하며, confluent-kafka 라이브러리를 사용합니다.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from confluent_kafka import KafkaException, Producer
from google.protobuf.message import Message as ProtobufMessage
from prometheus_client import Counter, Gauge, Histogram

from data_ingestion.domain.exceptions import PublishException
from data_ingestion.domain.models.market_data import MarketDataMessage
from data_ingestion.domain.ports.message_publisher import MessagePublisher

logger = logging.getLogger(__name__)

# ===== Prometheus Metrics =====
# 주의: 모듈 단위 등록. 테스트 프로세스 내 중복 import 환경이 아니라고 가정합니다.
KAFKA_PUBLISH_ATTEMPTS = Counter(
    "kafka_producer_publish_attempts_total",
    "Number of publish attempts",
    ["topic"],
)

KAFKA_PUBLISH_ENQUEUED = Counter(
    "kafka_producer_enqueued_total",
    "Number of messages enqueued to producer",
    ["topic"],
)

KAFKA_PUBLISH_BUFFER_FULL = Counter(
    "kafka_producer_buffer_full_total",
    "Number of BufferError occurrences during publish",
    ["topic"],
)

KAFKA_PUBLISH_RETRIES = Counter(
    "kafka_producer_retries_total",
    "Number of publish retries due to BufferError",
    ["topic"],
)

KAFKA_QUEUE_LENGTH = Gauge(
    "kafka_producer_queue_length",
    "Current length of producer internal queue",
)

KAFKA_DELIVERY_RESULTS = Counter(
    "kafka_producer_delivery_results_total",
    "Delivery results labeled by topic/result/error_code",
    ["topic", "result", "error_code"],
)

KAFKA_PUBLISH_LATENCY = Histogram(
    "kafka_producer_publish_latency_seconds",
    "Latency of publish operations",
    ["topic"],
)


class KafkaProducerAdapter(MessagePublisher):
    """
    Kafka Producer Adapter

    MessagePublisher 인터페이스를 구현하여 Protobuf 메시지를 Kafka로 발행합니다.

    Features:
        - 비동기 메시지 발행
        - 자동 재시도 (큐가 가득 찬 경우)
        - 전송 성공/실패 콜백
        - 리소스 관리 (컨텍스트 매니저 지원)

    Attributes:
        _config: Kafka Producer 설정
        _producer: confluent-kafka Producer 인스턴스
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        KafkaProducerAdapter를 초기화합니다.

        Args:
            config: Kafka Producer 설정 딕셔너리
                - bootstrap.servers: Kafka 브로커 주소 (필수)
                - client.id: 클라이언트 식별자
                - acks: 메시지 승인 레벨 (기본값: "all")
                - retries: 재시도 횟수
                - linger.ms: 배치 지연(ms) — 배치 전송 성능 향상 권장(기본 5)
                - compression.type: 압축 알고리즘 — lz4 권장(기본 lz4)
                - max.in.flight.requests.per.connection: 파이프라이닝 동시 요청 수(기본 5)
                - 기타 confluent-kafka Producer 설정

        Raises:
            ValueError: 필수 설정값이 누락된 경우
        """
        # 필수 설정값 검증
        if "bootstrap.servers" not in config:
            raise ValueError("bootstrap.servers is required in Kafka config")

        # 성능을 위한 권장 기본값을 먼저 세팅하고, 사용자 설정으로 덮어쓰게 합니다.
        # 주의: confluent-kafka(librdkafka)는 비동기 프로듀서이며 produce()는 non-blocking입니다.
        recommended_defaults: Dict[str, Any] = {
            "acks": "all",
            "compression.type": "lz4",
            "linger.ms": 5,
            # 파이프라이닝으로 네트워크 활용 극대화 (정렬 보장이 필요하면 5 유지)
            "max.in.flight.requests.per.connection": 5,
        }

        self._config = {**recommended_defaults, **config}

        # 에러 콜백 등록
        self._config["error_cb"] = self._error_callback

        # Producer 생성
        try:
            self._producer = Producer(self._config)
            logger.info(
                f"Initialized Kafka Producer: {config.get('bootstrap.servers')}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Producer: {e}", exc_info=True)
            raise PublishException(f"Failed to initialize Kafka Producer", cause=e)

    async def publish(
        self, topic: str, key: bytes, message: ProtobufMessage
    ) -> None:
        """
        Protobuf 메시지를 Kafka로 발행합니다.

        Args:
            topic: 메시지를 발행할 토픽 이름
            key: 파티션 키 (bytes)
            message: 발행할 Protobuf 메시지

        Raises:
            PublishException: 메시지 발행에 실패한 경우
        """
        try:
            # Protobuf 메시지 직렬화
            serialized_value = message.SerializeToString()

            # Kafka에 메시지 발행 (비동기)
            # BufferError가 발생할 수 있으므로 재시도 로직 포함
            max_retries = 10
            retry_count = 0

            # 관측성: 발행 시도 카운트
            KAFKA_PUBLISH_ATTEMPTS.labels(topic=topic).inc()

            while retry_count < max_retries:
                try:
                    self._producer.produce(
                        topic=topic,
                        key=key,
                        value=serialized_value,
                        callback=self._delivery_callback,
                    )
                    # 관측성: 내부 큐 적재 성공
                    KAFKA_PUBLISH_ENQUEUED.labels(topic=topic).inc()
                    break  # 성공 시 루프 탈출

                except BufferError:
                    # 큐가 가득 찬 경우 poll()로 공간 확보
                    logger.debug(f"Buffer full, polling... (retry {retry_count + 1})")
                    # 관측성: 버퍼 풀 및 재시도 카운트
                    KAFKA_PUBLISH_BUFFER_FULL.labels(topic=topic).inc()
                    KAFKA_PUBLISH_RETRIES.labels(topic=topic).inc()
                    self._producer.poll(0.1)
                    retry_count += 1
                    await asyncio.sleep(0.01)  # 짧은 대기

            if retry_count >= max_retries:
                raise PublishException(
                    f"Failed to publish message to {topic}: Buffer full after {max_retries} retries"
                )

            # 백그라운드에서 메시지 전송을 위해 poll 호출
            self._producer.poll(0)

            # 관측성: 현재 큐 길이 갱신
            try:
                KAFKA_QUEUE_LENGTH.set(len(self._producer))
            except Exception:
                # len() 미구현 등 예외는 관측성 비핵심이므로 무시
                pass

            logger.debug(f"Published message to topic: {topic}")

        except KafkaException as e:
            logger.error(f"Kafka error while publishing to {topic}: {e}", exc_info=True)
            raise PublishException(
                f"Failed to publish message to {topic}", cause=e
            )

        except Exception as e:
            logger.error(
                f"Unexpected error while publishing to {topic}: {e}", exc_info=True
            )
            raise PublishException(
                f"Failed to publish message to {topic}", cause=e
            )

    async def publish_market_data(
        self,
        topic: str,
        message: MarketDataMessage,
        protobuf_message: ProtobufMessage,
    ) -> None:
        """
        MarketDataMessage를 Kafka로 발행합니다.
        
        파티션 키는 자동으로 message.code로 설정되어 동일 마켓의 메시지가
        같은 파티션으로 전송되도록 보장합니다. 이를 통해 같은 마켓의 메시지는
        순서가 보장됩니다.
        
        Args:
            topic: Kafka 토픽 이름
            message: MarketDataMessage 도메인 객체 (키 추출용)
            protobuf_message: 전송할 Protobuf 메시지
        
        Raises:
            PublishException: 메시지 발행에 실패한 경우
        
        Examples:
            >>> async with KafkaProducerAdapter(config) as producer:
            ...     market_data = MarketDataMessage(...)
            ...     proto_message = market_data_pb2.TradeData(...)
            ...     await producer.publish_market_data(
            ...         topic="market-data",
            ...         message=market_data,
            ...         protobuf_message=proto_message
            ...     )
        """
        # 파티션 키: message.code (같은 마켓은 같은 파티션으로)
        key = message.code.encode("utf-8")
        
        # 지연 메트릭 기록
        with KAFKA_PUBLISH_LATENCY.labels(topic=topic).time():
            await self.publish(topic=topic, key=key, message=protobuf_message)

    async def flush(self, timeout: float = 5.0) -> int:
        """
        대기 중인 모든 메시지를 강제로 전송합니다.

        Args:
            timeout: 최대 대기 시간 (초)

        Returns:
            전송되지 못한 메시지 수 (0이면 모두 성공)

        Raises:
            PublishException: flush 작업 중 오류가 발생한 경우
        """
        try:
            # flush는 blocking이므로 asyncio.to_thread로 처리
            # 하지만 confluent-kafka의 flush는 빠르므로 직접 호출
            remaining = self._producer.flush(timeout=timeout)

            if remaining > 0:
                logger.warning(
                    f"Failed to flush {remaining} messages within {timeout}s timeout"
                )
            else:
                logger.debug(f"Successfully flushed all messages")

            return remaining

        except KafkaException as e:
            logger.error(f"Kafka error during flush: {e}", exc_info=True)
            raise PublishException(f"Failed to flush messages", cause=e)

        except Exception as e:
            logger.error(f"Unexpected error during flush: {e}", exc_info=True)
            raise PublishException(f"Failed to flush messages", cause=e)

    async def close(self) -> None:
        """
        Producer를 종료하고 모든 리소스를 해제합니다.

        종료 전에 대기 중인 모든 메시지를 flush합니다.
        """
        if not hasattr(self, "_producer") or self._producer is None:
            logger.debug("Producer already closed")
            return

        try:
            # 모든 메시지 flush (최대 10초 대기)
            remaining = await self.flush(timeout=10.0)

            if remaining > 0:
                logger.warning(
                    f"Closed producer with {remaining} unsent messages"
                )

            # Producer는 명시적으로 close하지 않아도 됨
            # (Python GC가 처리)
            self._producer = None
            logger.info("Kafka Producer closed successfully")

        except Exception as e:
            logger.error(f"Error while closing Kafka Producer: {e}", exc_info=True)
            # close 중 예외가 발생해도 종료는 계속 진행

    # ========== Private Methods ==========

    def _delivery_callback(self, err: Optional[Any], msg: Any) -> None:
        """
        메시지 전송 성공/실패 콜백

        Args:
            err: 에러 객체 (성공 시 None)
            msg: 전송된 메시지 객체
        """
        if err is not None:
            logger.error(
                f"Message delivery failed: {err.str()} "
                f"(error code: {err.code()})"
            )
            try:
                topic_label = msg.topic() if hasattr(msg, "topic") else "unknown"
                code_label = str(err.code() if hasattr(err, "code") else "unknown")
                KAFKA_DELIVERY_RESULTS.labels(
                    topic=topic_label, result="failure", error_code=code_label
                ).inc()
            except Exception:
                pass
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} "
                f"[partition: {msg.partition()}]"
            )
            try:
                topic_label = msg.topic() if hasattr(msg, "topic") else "unknown"
                KAFKA_DELIVERY_RESULTS.labels(
                    topic=topic_label, result="success", error_code="none"
                ).inc()
            except Exception:
                pass

    def _error_callback(self, err: Any) -> None:
        """
        Kafka 에러 콜백

        Args:
            err: Kafka 에러 객체
        """
        logger.error(
            f"Kafka error: {err.str()} (error code: {err.code()})"
        )

    # ========== Context Manager Support ==========

    async def __aenter__(self) -> "KafkaProducerAdapter":
        """Async context manager 진입"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager 종료"""
        await self.close()


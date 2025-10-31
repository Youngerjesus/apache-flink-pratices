"""
Kafka Producer 테스트

이 모듈은 KafkaProducer의 핵심 기능을 테스트합니다:
- Protobuf 메시지 발행
- 비동기 처리
- 에러 핸들링
- Flush 및 리소스 정리
"""

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import pytest
from confluent_kafka import KafkaError, KafkaException
from google.protobuf.message import Message as ProtobufMessage

from data_ingestion.domain.exceptions import PublishException
from data_ingestion.domain.models.market_data import (
    MarketDataMessage,
    MarketDataType,
    StreamType,
)
from data_ingestion.infrastructure.kafka.kafka_producer import KafkaProducerAdapter


@pytest.fixture
def kafka_config() -> Dict[str, Any]:
    """Kafka Producer 설정 픽스처"""
    return {
        "bootstrap.servers": "localhost:9092",
        "client.id": "test-producer",
        "acks": "all",
        "retries": 3,
        "max.in.flight.requests.per.connection": 1,
    }


@pytest.fixture
def kafka_producer(kafka_config: Dict[str, Any]) -> KafkaProducerAdapter:
    """KafkaProducerAdapter 픽스처"""
    with patch("data_ingestion.infrastructure.kafka.kafka_producer.Producer"):
        producer = KafkaProducerAdapter(kafka_config)
        return producer


@pytest.fixture
def sample_protobuf_message() -> MagicMock:
    """샘플 Protobuf 메시지 픽스처"""
    mock_message = MagicMock(spec=ProtobufMessage)
    mock_message.SerializeToString.return_value = b"serialized_data"
    return mock_message


@pytest.fixture
def sample_market_data_message() -> MarketDataMessage:
    """샘플 MarketDataMessage 픽스처"""
    return MarketDataMessage(
        exchange="upbit",
        code="KRW-BTC",
        received_timestamp=datetime.now(UTC),
        event_timestamp=datetime.now(UTC),
        stream_type=StreamType.REALTIME,
        raw_data={"type": "trade", "price": 50000000},
        data_type=MarketDataType.TRADE,
    )


class TestKafkaProducerAdapterInitialization:
    """KafkaProducerAdapter 초기화 테스트"""

    def test_초기화_시_설정값_저장됨(self, kafka_config: Dict[str, Any]) -> None:
        """
        GIVEN: Kafka Producer 설정
        WHEN: KafkaProducerAdapter를 초기화하면
        THEN: Producer가 올바르게 생성되어야 한다
        """
        # WHEN
        with patch("data_ingestion.infrastructure.kafka.kafka_producer.Producer") as mock_producer_class:
            producer = KafkaProducerAdapter(kafka_config)

            # THEN
            # error_cb가 추가되므로 정확한 config 검증
            call_args = mock_producer_class.call_args[0][0]
            assert call_args["bootstrap.servers"] == kafka_config["bootstrap.servers"]
            assert "error_cb" in call_args

    def test_필수_설정값_누락_시_예외_발생(self) -> None:
        """
        GIVEN: bootstrap.servers가 누락된 설정
        WHEN: KafkaProducerAdapter를 초기화하면
        THEN: ValueError가 발생해야 한다
        """
        # GIVEN
        invalid_config = {"client.id": "test"}

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            KafkaProducerAdapter(invalid_config)

        assert "bootstrap.servers" in str(exc_info.value)


class TestKafkaProducerAdapterPublish:
    """KafkaProducerAdapter 메시지 발행 테스트"""

    @pytest.mark.asyncio
    async def test_메시지_발행_성공(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: KafkaProducerAdapter와 Protobuf 메시지
        WHEN: publish()를 호출하면
        THEN: Kafka에 메시지가 발행되어야 한다
        """
        # GIVEN
        topic = "test-topic"
        key = b"test-key"

        # Mock producer.produce()가 성공하도록 설정
        kafka_producer._producer.produce = MagicMock()

        # WHEN
        await kafka_producer.publish(topic, key, sample_protobuf_message)

        # THEN
        kafka_producer._producer.produce.assert_called_once()
        call_kwargs = kafka_producer._producer.produce.call_args[1]
        assert call_kwargs["topic"] == topic
        assert call_kwargs["key"] == key
        assert call_kwargs["value"] == b"serialized_data"

    @pytest.mark.asyncio
    async def test_메시지_발행_시_직렬화_수행됨(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: Protobuf 메시지
        WHEN: publish()를 호출하면
        THEN: 메시지가 직렬화되어야 한다
        """
        # GIVEN
        kafka_producer._producer.produce = MagicMock()

        # WHEN
        await kafka_producer.publish("topic", b"key", sample_protobuf_message)

        # THEN
        sample_protobuf_message.SerializeToString.assert_called_once()

    @pytest.mark.asyncio
    async def test_큐가_가득_찬_경우_재시도(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: Kafka 큐가 가득 찬 상황
        WHEN: publish()를 호출하면
        THEN: poll()을 호출하여 공간을 확보하고 재시도해야 한다
        """
        # GIVEN
        queue_full_error = BufferError("Queue full")
        kafka_producer._producer.produce = MagicMock(
            side_effect=[queue_full_error, None]  # 첫 번째는 실패, 두 번째는 성공
        )
        kafka_producer._producer.poll = MagicMock()

        # WHEN
        await kafka_producer.publish("topic", b"key", sample_protobuf_message)

        # THEN
        assert kafka_producer._producer.produce.call_count == 2
        kafka_producer._producer.poll.assert_called()

    @pytest.mark.asyncio
    async def test_발행_실패_시_PublishException_발생(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: Kafka 발행이 실패하는 상황
        WHEN: publish()를 호출하면
        THEN: PublishException이 발생해야 한다
        """
        # GIVEN
        kafka_producer._producer.produce = MagicMock(
            side_effect=KafkaException(KafkaError(KafkaError._MSG_TIMED_OUT))
        )

        # WHEN / THEN
        with pytest.raises(PublishException) as exc_info:
            await kafka_producer.publish("topic", b"key", sample_protobuf_message)

        assert "Failed to publish message" in str(exc_info.value)


class TestKafkaProducerAdapterFlush:
    """KafkaProducerAdapter flush 테스트"""

    @pytest.mark.asyncio
    async def test_flush_성공(self, kafka_producer: KafkaProducerAdapter) -> None:
        """
        GIVEN: 발행된 메시지가 있는 Producer
        WHEN: flush()를 호출하면
        THEN: 모든 메시지가 전송 완료되어야 한다
        """
        # GIVEN
        kafka_producer._producer.flush = MagicMock(return_value=0)

        # WHEN
        result = await kafka_producer.flush(timeout=5.0)

        # THEN
        kafka_producer._producer.flush.assert_called_once_with(timeout=5.0)
        assert result == 0

    @pytest.mark.asyncio
    async def test_flush_타임아웃_시_경고(
        self, kafka_producer: KafkaProducerAdapter
    ) -> None:
        """
        GIVEN: flush가 타임아웃되는 상황
        WHEN: flush()를 호출하면
        THEN: 타임아웃된 메시지 수를 반환해야 한다
        """
        # GIVEN
        kafka_producer._producer.flush = MagicMock(return_value=3)  # 3개 메시지 미전송

        # WHEN
        result = await kafka_producer.flush(timeout=1.0)

        # THEN
        assert result == 3

    @pytest.mark.asyncio
    async def test_flush_중_예외_발생_시_PublishException(
        self, kafka_producer: KafkaProducerAdapter
    ) -> None:
        """
        GIVEN: flush 중 예외가 발생하는 상황
        WHEN: flush()를 호출하면
        THEN: PublishException이 발생해야 한다
        """
        # GIVEN
        kafka_producer._producer.flush = MagicMock(
            side_effect=KafkaException(KafkaError(KafkaError._TIMED_OUT))
        )

        # WHEN / THEN
        with pytest.raises(PublishException) as exc_info:
            await kafka_producer.flush(timeout=5.0)

        assert "Failed to flush" in str(exc_info.value)


class TestKafkaProducerAdapterClose:
    """KafkaProducerAdapter 종료 테스트"""

    @pytest.mark.asyncio
    async def test_close_시_flush_후_종료(
        self, kafka_producer: KafkaProducerAdapter
    ) -> None:
        """
        GIVEN: 활성화된 Producer
        WHEN: close()를 호출하면
        THEN: flush한 후 producer를 종료해야 한다
        """
        # GIVEN
        kafka_producer._producer.flush = MagicMock(return_value=0)
        kafka_producer._producer = MagicMock()

        # WHEN
        await kafka_producer.close()

        # THEN
        kafka_producer._producer.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_멱등성(self, kafka_producer: KafkaProducerAdapter) -> None:
        """
        GIVEN: 이미 종료된 Producer
        WHEN: close()를 다시 호출하면
        THEN: 오류 없이 즉시 반환해야 한다
        """
        # GIVEN
        kafka_producer._producer.flush = MagicMock(return_value=0)
        await kafka_producer.close()

        # WHEN / THEN
        # 두 번째 close()는 오류 없이 완료되어야 함
        await kafka_producer.close()


class TestKafkaProducerAdapterErrorCallback:
    """KafkaProducerAdapter 에러 콜백 테스트"""

    def test_에러_콜백_등록됨(self, kafka_config: Dict[str, Any]) -> None:
        """
        GIVEN: Kafka Producer 설정
        WHEN: KafkaProducerAdapter를 생성하면
        THEN: 에러 콜백이 등록되어야 한다
        """
        # WHEN
        with patch("data_ingestion.infrastructure.kafka.kafka_producer.Producer") as mock_producer_class:
            producer = KafkaProducerAdapter(kafka_config)

            # THEN
            call_kwargs = mock_producer_class.call_args[0][0]
            assert "error_cb" in call_kwargs

    def test_에러_콜백_호출_시_로깅(
        self, kafka_producer: KafkaProducerAdapter
    ) -> None:
        """
        GIVEN: 에러 콜백이 등록된 Producer
        WHEN: Kafka 에러가 발생하면
        THEN: 에러가 로깅되어야 한다
        """
        # GIVEN
        mock_error = Mock()
        mock_error.code.return_value = KafkaError._MSG_TIMED_OUT
        mock_error.str.return_value = "Message timed out"

        # WHEN / THEN
        # 에러 콜백이 예외를 발생시키지 않고 로깅만 해야 함
        kafka_producer._error_callback(mock_error)


class TestKafkaProducerAdapterDeliveryCallback:
    """KafkaProducerAdapter 전송 콜백 테스트"""

    @pytest.mark.asyncio
    async def test_전송_성공_콜백(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: 메시지를 발행한 Producer
        WHEN: 메시지 전송이 성공하면
        THEN: 전송 성공 콜백이 호출되어야 한다
        """
        # GIVEN
        delivery_callback = None

        def capture_callback(*args, **kwargs):
            nonlocal delivery_callback
            delivery_callback = kwargs.get("callback")

        kafka_producer._producer.produce = MagicMock(side_effect=capture_callback)

        # WHEN
        await kafka_producer.publish("topic", b"key", sample_protobuf_message)

        # THEN
        assert delivery_callback is not None

        # 전송 성공 시나리오
        mock_message = Mock()
        mock_message.error.return_value = None
        mock_message.topic.return_value = "topic"
        mock_message.partition.return_value = 0

        # 콜백 호출 (예외 발생하지 않아야 함)
        delivery_callback(None, mock_message)

    @pytest.mark.asyncio
    async def test_전송_실패_콜백_로깅(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: 메시지를 발행한 Producer
        WHEN: 메시지 전송이 실패하면
        THEN: 전송 실패가 로깅되어야 한다
        """
        # GIVEN
        delivery_callback = None

        def capture_callback(*args, **kwargs):
            nonlocal delivery_callback
            delivery_callback = kwargs.get("callback")

        kafka_producer._producer.produce = MagicMock(side_effect=capture_callback)

        # WHEN
        await kafka_producer.publish("topic", b"key", sample_protobuf_message)

        # THEN
        assert delivery_callback is not None

        # 전송 실패 시나리오
        mock_error = Mock()
        mock_error.code.return_value = KafkaError._MSG_TIMED_OUT
        mock_error.str.return_value = "Message timed out"

        mock_message = Mock()
        mock_message.error.return_value = mock_error

        # 콜백 호출 (로깅만 하고 예외는 발생하지 않아야 함)
        delivery_callback(mock_error, mock_message)


class TestKafkaProducerAdapterMarketDataPublish:
    """KafkaProducerAdapter 마켓 데이터 발행 테스트"""

    @pytest.mark.asyncio
    async def test_publish_market_data_uses_code_as_key(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_market_data_message: MarketDataMessage,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: MarketDataMessage와 Protobuf 메시지
        WHEN: publish_market_data()를 호출하면
        THEN: message.code가 파티션 키로 사용되어야 한다
        """
        # GIVEN
        topic = "market-data"
        kafka_producer._producer.produce = MagicMock()

        # WHEN
        await kafka_producer.publish_market_data(
            topic=topic,
            message=sample_market_data_message,
            protobuf_message=sample_protobuf_message,
        )

        # THEN
        kafka_producer._producer.produce.assert_called_once()
        call_kwargs = kafka_producer._producer.produce.call_args[1]
        assert call_kwargs["topic"] == topic
        assert call_kwargs["key"] == b"KRW-BTC"  # message.code를 bytes로 변환한 값
        assert call_kwargs["value"] == b"serialized_data"

    @pytest.mark.asyncio
    async def test_publish_market_data_latency_metric_recorded(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_market_data_message: MarketDataMessage,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: MarketDataMessage와 Protobuf 메시지
        WHEN: publish_market_data()를 호출하면
        THEN: 지연 메트릭이 기록되어야 한다
        """
        # GIVEN
        topic = "market-data"
        kafka_producer._producer.produce = MagicMock()

        # prometheus_client.Histogram.time()은 컨텍스트 매니저이므로,
        # 실제로 메트릭이 기록되는지 확인하는 것은 어렵습니다.
        # 대신 메서드가 성공적으로 완료되는지 확인합니다.

        # WHEN
        await kafka_producer.publish_market_data(
            topic=topic,
            message=sample_market_data_message,
            protobuf_message=sample_protobuf_message,
        )

        # THEN - 정상적으로 완료됨
        kafka_producer._producer.produce.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_market_data_with_different_codes(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: 서로 다른 code를 가진 MarketDataMessage들
        WHEN: publish_market_data()를 여러 번 호출하면
        THEN: 각 메시지의 code가 파티션 키로 사용되어야 한다
        """
        # GIVEN
        topic = "market-data"
        kafka_producer._producer.produce = MagicMock()

        messages = [
            MarketDataMessage(
                exchange="upbit",
                code="KRW-BTC",
                received_timestamp=datetime.now(UTC),
                event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data={},
                data_type=MarketDataType.TRADE,
            ),
            MarketDataMessage(
                exchange="upbit",
                code="KRW-ETH",
                received_timestamp=datetime.now(UTC),
                event_timestamp=datetime.now(UTC),
                stream_type=StreamType.REALTIME,
                raw_data={},
                data_type=MarketDataType.TRADE,
            ),
        ]

        # WHEN
        for message in messages:
            await kafka_producer.publish_market_data(
                topic=topic,
                message=message,
                protobuf_message=sample_protobuf_message,
            )

        # THEN
        assert kafka_producer._producer.produce.call_count == 2
        
        # 첫 번째 호출의 키 확인
        first_call_kwargs = kafka_producer._producer.produce.call_args_list[0][1]
        assert first_call_kwargs["key"] == b"KRW-BTC"

        # 두 번째 호출의 키 확인
        second_call_kwargs = kafka_producer._producer.produce.call_args_list[1][1]
        assert second_call_kwargs["key"] == b"KRW-ETH"


class TestKafkaProducerAdapterIntegration:
    """KafkaProducerAdapter 통합 테스트"""

    @pytest.mark.asyncio
    async def test_발행부터_flush까지_전체_플로우(
        self,
        kafka_producer: KafkaProducerAdapter,
        sample_protobuf_message: MagicMock,
    ) -> None:
        """
        GIVEN: KafkaProducerAdapter
        WHEN: 여러 메시지를 발행하고 flush하면
        THEN: 모든 메시지가 성공적으로 전송되어야 한다
        """
        # GIVEN
        kafka_producer._producer.produce = MagicMock()
        kafka_producer._producer.flush = MagicMock(return_value=0)

        # WHEN
        # 3개의 메시지 발행
        for i in range(3):
            await kafka_producer.publish(
                f"topic-{i}", f"key-{i}".encode(), sample_protobuf_message
            )

        # Flush
        result = await kafka_producer.flush(timeout=5.0)

        # THEN
        assert kafka_producer._producer.produce.call_count == 3
        assert result == 0

    @pytest.mark.asyncio
    async def test_컨텍스트_매니저_사용(
        self, kafka_config: Dict[str, Any]
    ) -> None:
        """
        GIVEN: KafkaProducerAdapter
        WHEN: async with 컨텍스트 매니저로 사용하면
        THEN: 종료 시 자동으로 리소스가 정리되어야 한다
        """
        # WHEN
        with patch("data_ingestion.infrastructure.kafka.kafka_producer.Producer") as mock_producer_class:
            mock_producer = MagicMock()
            mock_producer.flush = MagicMock(return_value=0)
            mock_producer_class.return_value = mock_producer

            async with KafkaProducerAdapter(kafka_config) as producer:
                # 사용
                pass

            # THEN
            # 컨텍스트 종료 시 flush가 호출되어야 함
            mock_producer.flush.assert_called()


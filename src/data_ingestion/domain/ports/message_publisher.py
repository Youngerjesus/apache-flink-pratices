"""
메시지 발행자 포트 인터페이스

Kafka와 같은 메시지 브로커로 데이터를 발행하는 발행자의 추상 인터페이스입니다.
Domain Layer는 이 인터페이스에만 의존하며, 실제 구현은 Infrastructure Layer에서 제공됩니다.

이 패턴은 Hexagonal Architecture (Ports and Adapters)의 핵심으로,
Domain Logic과 External System(Kafka) 간의 결합도를 낮춥니다.
"""

from abc import ABC, abstractmethod

from data_ingestion.domain.models.market_data import MarketDataMessage


class MessagePublisher(ABC):
    """
    메시지 발행자 포트 인터페이스

    시장 데이터 메시지를 메시지 브로커(Kafka)로 발행하는 추상 인터페이스입니다.
    모든 메시지 발행자 구현체는 이 인터페이스를 준수해야 합니다.

    Architecture Note:
        - Port: Domain Layer가 정의하는 인터페이스
        - Adapter: Infrastructure Layer가 제공하는 실제 구현체 (KafkaPublisher)
        - Domain Layer는 이 Port에만 의존하며, Kafka를 직접 알지 못함

    Implementation Requirements:
        1. publish()는 메시지를 버퍼에 추가하는 비동기 작업이어야 함
        2. flush()는 버퍼의 모든 메시지를 실제로 전송해야 함
        3. close()는 모든 리소스를 정리하고 연결을 종료해야 함
        4. publish() 실패 시 PublishException을 발생시켜야 함

    Examples:
        >>> # 실제 사용 예시 (Infrastructure Layer에서 구현체 제공)
        >>> from infrastructure.kafka import KafkaPublisher
        >>> 
        >>> publisher: MessagePublisher = KafkaPublisher(config)
        >>> 
        >>> # 메시지 발행
        >>> await publisher.publish(message)
        >>> 
        >>> # 버퍼 플러시
        >>> await publisher.flush()
        >>> 
        >>> # 리소스 정리
        >>> await publisher.close()
    """

    @abstractmethod
    async def publish(self, message: MarketDataMessage) -> None:
        """
        메시지 발행

        시장 데이터 메시지를 메시지 브로커로 발행합니다.
        이 메서드는 일반적으로 메시지를 버퍼에 추가하고 즉시 반환합니다.
        실제 전송은 flush() 호출 시 또는 자동으로 이루어집니다.

        Args:
            message: 발행할 시장 데이터 메시지

        Raises:
            PublishException: 발행 실패 시

        Examples:
            >>> from datetime import datetime, UTC
            >>> from domain.models.market_data import MarketDataMessage, StreamType
            >>> 
            >>> publisher = KafkaPublisher(config)
            >>> message = MarketDataMessage(
            ...     exchange="upbit",
            ...     code="KRW-BTC",
            ...     timestamp=datetime.now(UTC),
            ...     stream_type=StreamType.REALTIME,
            ...     raw_data={"price": 50000000}
            ... )
            >>> await publisher.publish(message)

        Note:
            - 이 메서드는 멱등(idempotent)하지 않습니다
            - 동일한 메시지를 여러 번 호출하면 여러 번 발행됩니다
            - 성능을 위해 배치 전송을 권장합니다
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """
        버퍼 플러시

        버퍼에 있는 모든 메시지를 즉시 메시지 브로커로 전송합니다.
        이 메서드는 모든 메시지가 성공적으로 전송될 때까지 대기합니다.

        Raises:
            PublishException: 플러시 실패 시

        Examples:
            >>> publisher = KafkaPublisher(config)
            >>> 
            >>> # 여러 메시지 발행
            >>> for message in messages:
            ...     await publisher.publish(message)
            >>> 
            >>> # 모든 메시지를 즉시 전송
            >>> await publisher.flush()

        Note:
            - 성능에 영향을 줄 수 있으므로 필요한 경우에만 호출하세요
            - 일반적으로 배치 작업 완료 시 또는 애플리케이션 종료 시 호출합니다
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        리소스 정리 및 연결 종료

        모든 미전송 메시지를 전송하고, 리소스를 정리한 후 연결을 종료합니다.
        이 메서드는 애플리케이션 종료 시 반드시 호출되어야 합니다.

        Examples:
            >>> publisher = KafkaPublisher(config)
            >>> 
            >>> try:
            ...     # 메시지 발행 작업
            ...     await publisher.publish(message)
            ... finally:
            ...     # 리소스 정리
            ...     await publisher.close()

        Note:
            - 이 메서드는 멱등(idempotent)해야 합니다
            - 여러 번 호출해도 안전해야 합니다
            - close() 호출 후 publish()를 호출하면 예외가 발생해야 합니다
        """
        pass



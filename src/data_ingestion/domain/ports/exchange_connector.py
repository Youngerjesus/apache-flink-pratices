"""
거래소 커넥터 포트 인터페이스

거래소와의 연결을 담당하는 커넥터의 추상 인터페이스입니다.
Domain Layer는 이 인터페이스에만 의존하며, 실제 구현은 Infrastructure Layer에서 제공됩니다.

이 패턴은 Hexagonal Architecture (Ports and Adapters)의 핵심으로,
Domain Logic과 External System(거래소 API) 간의 결합도를 낮춥니다.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.market_data import MarketDataMessage


class ExchangeConnector(ABC):
    """
    거래소 커넥터 포트 인터페이스

    거래소와의 WebSocket 연결 및 실시간 데이터 스트리밍을 담당하는 추상 인터페이스입니다.
    모든 거래소 커넥터 구현체는 이 인터페이스를 준수해야 합니다.

    Architecture Note:
        - Port: Domain Layer가 정의하는 인터페이스
        - Adapter: Infrastructure Layer가 제공하는 실제 구현체
        - Domain Layer는 이 Port에만 의존하며, 구체적인 구현을 알지 못함

    Implementation Requirements:
        1. connect()와 disconnect()는 멱등(idempotent)해야 함
        2. stream_market_data()는 연결이 끊어지면 자동으로 종료되어야 함
        3. get_connection_state()는 현재 연결 상태를 실시간으로 반영해야 함
        4. 모든 예외는 Domain Layer의 예외로 변환되어야 함

    Examples:
        >>> # 실제 사용 예시 (Infrastructure Layer에서 구현체 제공)
        >>> from infrastructure.connectors import UpbitConnector
        >>> 
        >>> connector: ExchangeConnector = UpbitConnector(config)
        >>> await connector.connect()
        >>> 
        >>> async for message in connector.stream_market_data():
        ...     print(f"Received: {message.code} @ {message.timestamp}")
        >>> 
        >>> await connector.disconnect()
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        거래소에 연결

        WebSocket 연결을 수립하고 필요한 초기화를 수행합니다.
        이 메서드는 멱등(idempotent)해야 하며, 이미 연결된 상태에서 호출해도 안전해야 합니다.

        Raises:
            ConnectionException: 연결 실패 시

        Examples:
            >>> connector = UpbitConnector(config)
            >>> await connector.connect()
            >>> # 상태가 CONNECTED로 변경됨
            >>> assert connector.get_connection_state() == ConnectionState.CONNECTED
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        거래소 연결 해제

        WebSocket 연결을 정상적으로 종료하고 리소스를 정리합니다.
        이 메서드는 멱등(idempotent)해야 하며, 이미 연결 해제된 상태에서 호출해도 안전해야 합니다.

        Examples:
            >>> connector = UpbitConnector(config)
            >>> await connector.connect()
            >>> await connector.disconnect()
            >>> # 상태가 DISCONNECTED로 변경됨
            >>> assert connector.get_connection_state() == ConnectionState.DISCONNECTED
        """
        pass

    @abstractmethod
    async def stream_market_data(self) -> AsyncIterator[MarketDataMessage]:
        """
        실시간 시장 데이터 스트리밍

        WebSocket을 통해 수신한 실시간 시장 데이터를 MarketDataMessage로 변환하여
        비동기 이터레이터로 제공합니다.

        이 메서드는 연결이 끊어지면 자동으로 종료되어야 하며,
        재연결이 필요한 경우 ConnectionException을 발생시켜야 합니다.

        Yields:
            MarketDataMessage: 실시간 시장 데이터 메시지

        Raises:
            ConnectionException: 연결이 끊어진 경우
            ValidationException: 데이터 검증 실패 시

        Examples:
            >>> connector = UpbitConnector(config)
            >>> await connector.connect()
            >>> 
            >>> async for message in connector.stream_market_data():
            ...     print(f"{message.code}: {message.raw_data}")
            ...     if some_condition:
            ...         break
            >>> 
            >>> await connector.disconnect()

        Note:
            - 이 메서드는 long-running generator로 동작합니다
            - 연결이 끊어지면 자동으로 종료됩니다
            - 무한 루프를 방지하기 위해 타임아웃 설정을 권장합니다
        """
        pass

    @abstractmethod
    def get_connection_state(self) -> ConnectionState:
        """
        현재 연결 상태 조회

        Returns:
            ConnectionState: 현재 연결 상태

        Examples:
            >>> connector = UpbitConnector(config)
            >>> connector.get_connection_state()
            <ConnectionState.DISCONNECTED: 'disconnected'>
            >>> 
            >>> await connector.connect()
            >>> connector.get_connection_state()
            <ConnectionState.CONNECTED: 'connected'>
        """
        pass



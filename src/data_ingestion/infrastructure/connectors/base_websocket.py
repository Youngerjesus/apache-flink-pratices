"""
Base WebSocket Connector 구현

이 모듈은 WebSocket 기반 거래소 커넥터의 공통 기능을 제공합니다:
- 연결 생명주기 관리 (connect, disconnect, reconnect)
- 자동 재연결 및 지수 백오프
- Ping/Pong 처리로 연결 유지
- 상태 전환 검증 및 추적
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict

import websockets
from websockets.client import WebSocketClientProtocol

from data_ingestion.domain.exceptions import (
    ConnectionClosedError,
    ConnectionException,
    ConnectionFailedError,
    InvalidMessageError,
)
from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import MarketDataMessage
from data_ingestion.domain.ports.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)


class BaseWebSocketConnector(ExchangeConnector, ABC):
    """
    WebSocket 기반 거래소 커넥터의 추상 기본 클래스입니다.

    이 클래스는 WebSocket 연결 관리, 재연결, Ping/Pong 처리 등의
    공통 기능을 제공하며, 거래소별 구현체는 메시지 파싱과 구독 로직만
    구현하면 됩니다.

    Attributes:
        _config: 거래소 연결 설정
        _state: 현재 연결 상태
        _websocket: WebSocket 연결 객체
        _reconnect_attempts: 현재까지의 재연결 시도 횟수
        _connect_lock: 동시 연결 방지를 위한 락
        _connecting_task: 현재 진행 중인 연결 태스크 (단일 비행 패턴)
    """

    def __init__(self, config: ExchangeConfig) -> None:
        """
        BaseWebSocketConnector를 초기화합니다.

        Args:
            config: 거래소 연결 설정
        """
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._websocket: WebSocketClientProtocol | None = None
        self._reconnect_attempts = 0
        self._connect_lock = asyncio.Lock()  # 동시성 제어
        self._connecting_task: asyncio.Task | None = None  # 단일 비행 패턴

        logger.info(
            f"Initialized {self.__class__.__name__} for {config.exchange_name}"
        )

    async def connect(self) -> None:
        """
        거래소 WebSocket 연결을 수립하고 초기화합니다.

        연결 과정:
        1. 상태를 CONNECTING으로 변경
        2. WebSocket 연결 수립
        3. 구독 메시지 전송 (거래소별 구현)
        4. 상태를 CONNECTED로 변경

        멱등성 및 동시성 제어:
        - 이미 CONNECTED 상태면 즉시 반환 (멱등성)
        - 동시 호출 시 첫 번째 연결만 수행 (단일 비행 패턴)
        - 락을 사용하여 상태 전환의 원자성 보장

        Raises:
            ConnectionFailedError: 연결 수립에 실패한 경우
        """
        # 첫 번째 체크: 락 없이 빠른 반환 (이미 연결됨)
        if self._state == ConnectionState.CONNECTED:
            logger.debug("Already connected, skipping connect()")
            return

        # 단일 비행 패턴: 연결 중인 태스크가 있으면 그것을 await
        if self._connecting_task is not None and not self._connecting_task.done():
            logger.debug("Connection already in progress, waiting for it to complete")
            try:
                await self._connecting_task
                return
            except Exception:
                # 기존 연결 시도가 실패했으면 새로 시도
                pass

        # 락 획득하여 동시 연결 방지
        async with self._connect_lock:
            # 두 번째 체크: 락을 획득한 후 다시 확인 (더블 체크)
            if self._state == ConnectionState.CONNECTED:
                logger.debug("Already connected (double-check), skipping connect()")
                return

            # 연결 중인 태스크가 있으면 대기
            if self._connecting_task is not None and not self._connecting_task.done():
                logger.debug("Connection task exists (double-check), waiting")
                try:
                    await self._connecting_task
                    return
                except Exception:
                    pass

            # 새 연결 시도: 현재 Task를 _connecting_task에 저장
            current_task = asyncio.current_task()
            self._connecting_task = current_task

            try:
                # 상태 전환: DISCONNECTED -> CONNECTING
                self._transition_state(ConnectionState.CONNECTING)

                # WebSocket 연결 수립
                logger.info(f"Connecting to {self._config.websocket_url}...")
                self._websocket = await websockets.connect(
                    self._config.websocket_url,
                    ping_interval=self._config.ping_interval_seconds,  # websockets 라이브러리 자동 핑
                    ping_timeout=30,  # pong 미수신 시 30초 후 연결 종료
                )

                # 구독 메시지 전송 (거래소별 구현)
                await self._send_subscription_message()

                # 상태 전환: CONNECTING -> CONNECTED
                self._transition_state(ConnectionState.CONNECTED)
                self._reconnect_attempts = 0  # 성공 시 재시도 카운터 리셋

                logger.info(f"Successfully connected to {self._config.exchange_name}")

            except Exception as e:
                logger.error(f"Failed to connect: {e}", exc_info=True)
                self._transition_state(ConnectionState.FAILED)
                await self._cleanup()
                raise ConnectionFailedError(
                    f"Failed to connect to {self._config.websocket_url}", cause=e
                )
            finally:
                # 연결 시도 완료 후 태스크 정리
                if self._connecting_task == current_task:
                    self._connecting_task = None

    async def disconnect(self) -> None:
        """
        현재 활성화된 WebSocket 연결을 종료하고 모든 관련 리소스를 정리합니다.

        멱등성 및 동시성 제어:
        - 이미 DISCONNECTED 상태면 즉시 반환 (멱등성)
        - 락을 사용하여 동시 disconnect 호출 시 안전하게 처리
        """
        # 첫 번째 체크: 락 없이 빠른 반환
        if self._state == ConnectionState.DISCONNECTED:
            logger.debug("Already disconnected, skipping disconnect()")
            return

        # 락 획득하여 동시 disconnect 방지
        async with self._connect_lock:
            # 두 번째 체크: 락을 획득한 후 다시 확인 (더블 체크)
            if self._state == ConnectionState.DISCONNECTED:
                logger.debug("Already disconnected (double-check), skipping disconnect()")
                return

            logger.info(f"Disconnecting from {self._config.exchange_name}...")

            # 리소스 정리
            await self._cleanup()

            # 상태 전환
            self._transition_state(ConnectionState.DISCONNECTED)

            logger.info(f"Disconnected from {self._config.exchange_name}")

    def get_state(self) -> ConnectionState:
        """
        현재 연결 상태를 반환합니다.

        Returns:
            ConnectionState: 현재 연결 상태
        """
        return self._state

    async def stream_market_data(self) -> AsyncIterator[MarketDataMessage]:
        """
        거래소로부터 실시간 시장 데이터 스트림을 비동기적으로 제공합니다.

        이 메서드는 연결이 활성화된 동안 계속해서 MarketDataMessage 객체를
        yield 합니다. 연결이 끊기면 자동으로 재연결을 시도합니다.

        Yields:
            MarketDataMessage: 거래소로부터 수신된 시장 데이터 메시지

        Raises:
            ConnectionClosedError: 재연결 시도가 최대 횟수를 초과한 경우
        """
        while True:
            try:
                # 연결 확인 및 필요 시 연결 수립
                if self._state != ConnectionState.CONNECTED:
                    await self.connect()

                # WebSocket으로부터 메시지 수신
                if self._websocket is None:
                    raise ConnectionClosedError("WebSocket is not connected")

                raw_message = await self._websocket.recv()

                # 메시지 파싱 (거래소별 구현)
                parsed_data = await self._parse_message(raw_message)

                if parsed_data:
                    # MarketDataMessage로 변환하여 yield
                    # (실제로는 서브클래스에서 더 구체적인 변환이 필요)
                    # 여기서는 기본 구조만 제공
                    messages = self._convert_to_market_data_messages(parsed_data)
                    for message in messages:
                        yield message

            except asyncio.CancelledError:
                # 그레이스풀 종료: 재연결 없이 즉시 전파
                logger.info("Stream cancelled, shutting down gracefully")
                raise

            except websockets.exceptions.ConnectionClosed as e:
                # 연결 계층 에러: 재연결 시도
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_connection_closed()

            except (OSError, asyncio.TimeoutError, TimeoutError) as e:
                # 네트워크/타임아웃 에러: 재연결 시도
                logger.warning(f"Network/Timeout error: {e}")
                await self._handle_connection_closed()

            except (json.JSONDecodeError, InvalidMessageError) as e:
                # 파싱/애플리케이션 에러: 로그만, 재연결 없이 계속
                logger.warning(f"Message parsing error (no reconnect): {e}")
                continue

            except Exception as e:
                # 기타 예상치 못한 에러: 재연결 시도
                logger.error(f"Unexpected error in stream_market_data: {e}", exc_info=True)
                await self._handle_connection_closed()

    async def get_connection_state(self) -> ConnectionState:
        """
        현재 커넥터의 연결 상태를 반환합니다.

        Returns:
            ConnectionState: 현재 연결 상태
        """
        return self._state

    # ========== Private Methods: Connection Management ==========

    def _transition_state(self, target_state: ConnectionState) -> None:
        """
        상태 전환을 수행합니다.

        Args:
            target_state: 전환할 목표 상태

        Raises:
            InvalidTransitionError: 허용되지 않는 상태 전환인 경우
        """
        self._state.validate_transition(target_state)
        logger.debug(f"State transition: {self._state.name} -> {target_state.name}")
        self._state = target_state

    async def _cleanup(self) -> None:
        """
        모든 리소스를 정리합니다.

        - WebSocket 연결 종료
        """
        # WebSocket 연결 종료
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
            self._websocket = None

    # ========== Private Methods: Reconnection ==========

    async def _handle_connection_closed(self) -> None:
        """
        연결 종료 상황을 처리하고 재연결을 시도합니다.

        Raises:
            ConnectionClosedError: 최대 재연결 시도 횟수를 초과한 경우
        """
        logger.warning("Connection closed, attempting to reconnect...")

        # 상태 전환: 현재 상태에 따라 안전하게 전환
        # CONNECTED인 경우에만 RECONNECTING으로 전환, FAILED인 경우 DISCONNECTED로 정리
        if self._state == ConnectionState.CONNECTED:
            self._transition_state(ConnectionState.RECONNECTING)
        elif self._state == ConnectionState.FAILED:
            self._transition_state(ConnectionState.DISCONNECTED)

        # 리소스 정리
        await self._cleanup()

        # 재연결 시도
        while self._should_attempt_reconnect():
            self._reconnect_attempts += 1
            delay = self._calculate_backoff_delay()

            logger.info(
                f"Reconnection attempt {self._reconnect_attempts}/"
                f"{self._config.max_reconnect_attempts} in {delay:.2f}s..."
            )

            await asyncio.sleep(delay)

            # 재연결 전에 DISCONNECTED로 상태 전환 (상태 전환 규칙 준수)
            self._transition_state(ConnectionState.DISCONNECTED)

            try:
                await self.connect()
                logger.info("Reconnection successful")
                return
            except ConnectionFailedError:
                logger.warning(f"Reconnection attempt {self._reconnect_attempts} failed")
                # 실패 시 다음 루프를 위해 DISCONNECTED 상태로 정리
                if self._state != ConnectionState.DISCONNECTED:
                    self._transition_state(ConnectionState.DISCONNECTED)

        # 최대 재연결 시도 횟수 초과
        if self._state in (
            ConnectionState.CONNECTING,
            ConnectionState.CONNECTED,
            ConnectionState.RECONNECTING,
        ):
            self._transition_state(ConnectionState.FAILED)
        raise ConnectionClosedError(
            f"Failed to reconnect after {self._reconnect_attempts} attempts"
        )

    def _should_attempt_reconnect(self) -> bool:
        """
        재연결을 시도해야 하는지 판단합니다.

        Returns:
            재연결을 시도해야 하면 True, 아니면 False
        """
        max_attempts = self._config.max_reconnect_attempts
        # max_reconnect_attempts가 0이면 무한 재시도
        if max_attempts == 0:
            return True
        return self._reconnect_attempts < max_attempts

    def _calculate_backoff_delay(self) -> float:
        """
        지수 백오프 지연 시간을 계산합니다.

        Returns:
            지연 시간 (초)

        Examples:
            - 0번째 시도: 1초
            - 1번째 시도: 2초
            - 2번째 시도: 4초
            - ...
            - max_seconds를 초과하지 않음
        """
        # 지수 백오프: 2^n
        delay = min(
            2**self._reconnect_attempts,
            self._config.exponential_backoff_max_seconds,
        )
        return float(delay)

    # ========== Abstract Methods: Subclass Implementation ==========

    @abstractmethod
    async def _send_subscription_message(self) -> None:
        """
        거래소에 구독 메시지를 전송합니다.

        서브클래스에서 거래소별 구독 메시지 형식에 맞게 구현해야 합니다.

        Example:
            await self._websocket.send(json.dumps({
                "type": "subscribe",
                "channels": ["orderbook", "trade"]
            }))

        Raises:
            ConnectionException: 구독 메시지 전송에 실패한 경우
        """
        raise NotImplementedError

    @abstractmethod
    async def _parse_message(self, raw_message: str) -> Dict[str, Any] | None:
        """
        거래소로부터 수신한 원시 메시지를 파싱합니다.

        서브클래스에서 거래소별 메시지 형식에 맞게 구현해야 합니다.

        Args:
            raw_message: 거래소로부터 수신한 원시 메시지 (JSON 문자열)

        Returns:
            파싱된 메시지 딕셔너리, 또는 파싱 실패 시 None

        Example:
            parsed = json.loads(raw_message)
            if parsed.get("type") == "orderbook":
                return parsed
            return None
        """
        raise NotImplementedError

    def _convert_to_market_data_messages(
        self, parsed_data: Dict[str, Any]
    ) -> list[MarketDataMessage]:
        """
        파싱된 데이터를 MarketDataMessage 객체 리스트로 변환합니다.

        서브클래스에서 필요 시 오버라이드할 수 있습니다.

        Args:
            parsed_data: 파싱된 메시지 데이터

        Returns:
            MarketDataMessage 객체 리스트 (기본 구현은 빈 리스트 반환)
        """
        # 기본 구현: 빈 리스트 반환
        # 서브클래스에서 실제 변환 로직 구현
        return []


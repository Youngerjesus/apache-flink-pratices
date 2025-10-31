"""
Upbit WebSocket Connector 구현

이 모듈은 업비트 거래소의 WebSocket API와 연결하여 실시간 시장 데이터를 수집합니다.
업비트 특화 메시지 형식 처리 및 구독 관리를 담당합니다.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from data_ingestion.domain.exceptions import ConnectionException, InvalidMessageError
from data_ingestion.domain.models.exchange_config import ExchangeConfig
from data_ingestion.domain.models.market_data import (
    MarketDataMessage,
    MarketDataType,
    StreamType,
)
from data_ingestion.infrastructure.connectors.base_websocket import (
    BaseWebSocketConnector,
)
from data_ingestion.infrastructure.serialization.json_utils import (
    json_dumps,
    json_loads,
)

logger = logging.getLogger(__name__)


class UpbitWebSocketConnector(BaseWebSocketConnector):
    """
    업비트 거래소 WebSocket 커넥터

    업비트의 실시간 데이터 API를 통해 거래(Trade)와 호가(OrderBook) 데이터를 수집합니다.

    업비트 WebSocket API 형식:
        - 구독 메시지: [{"ticket":"UUID"}, {"type":"trade","codes":["KRW-BTC"]}, {"format":"DEFAULT"}]
        - Trade 메시지: {"type":"trade", "code":"KRW-BTC", "trade_price":..., ...}
        - OrderBook 메시지: {"type":"orderbook", "code":"KRW-BTC", "orderbook_units":[...], ...}

    Attributes:
        _config: 업비트 연결 설정
    """

    def __init__(self, config: ExchangeConfig) -> None:
        """
        UpbitWebSocketConnector를 초기화합니다.

        Args:
            config: 업비트 거래소 연결 설정
        """
        super().__init__(config)
        logger.info(f"Initialized UpbitWebSocketConnector for {len(config.subscribed_markets)} markets")
        # 구독 레지스트리 (ticket -> SubscriptionEntry)
        self._subscriptions: Dict[str, SubscriptionEntry] = {}
        # 코드별 ticket 역인덱스
        self._code_to_tickets: Dict[str, set[str]] = {}

    async def _send_subscription_message(self) -> None:
        """
        업비트에 구독 메시지를 전송합니다.
        
        재연결 시 기존 구독을 복원하거나, 최초 연결 시 초기 구독을 생성합니다.

        업비트는 다음 형식의 구독 메시지를 요구합니다:
        [
            {"ticket": "UNIQUE_TICKET"},
            {"type": "trade", "codes": ["KRW-BTC", "KRW-ETH"]},
            {"type": "orderbook", "codes": ["KRW-BTC", "KRW-ETH"]},
            {"format": "DEFAULT"}
        ]

        Raises:
            ConnectionException: 구독 메시지 전송에 실패한 경우
        """
        if not self._websocket:
            raise ConnectionException("WebSocket is not connected")

        try:
            if not self._subscriptions:
                # 초기 시딩: trade/orderbook 각각 구성된 마켓으로 생성
                market_codes = list(self._config.subscribed_markets)
                await self._seed_initial_subscriptions(market_codes)
            else:
                # 기존 구독 재전송 (재연결 시)
                for entry in self._subscriptions.values():
                    await self._send_single_subscription(entry.ticket, entry.sub_type, entry.codes)

        except Exception as e:
            logger.error(f"Failed to send subscription message: {e}", exc_info=True)
            raise ConnectionException(f"Failed to send subscription message", cause=e)

    async def _parse_message(self, raw_message: str) -> Dict[str, Any] | None:
        """
        업비트로부터 수신한 원시 메시지를 파싱합니다.

        Args:
            raw_message: 업비트로부터 수신한 원시 메시지 (JSON 문자열)

        Returns:
            파싱된 메시지 딕셔너리, 또는 파싱 실패/무효한 메시지인 경우 None

        업비트 메시지 형식:
            Trade: {
                "type": "trade",
                "code": "KRW-BTC",
                "trade_price": 50000000.0,
                "trade_volume": 0.01,
                "ask_bid": "BID",
                ...
            }

            OrderBook: {
                "type": "orderbook",
                "code": "KRW-BTC",
                "total_ask_size": 10.5,
                "total_bid_size": 15.3,
                "orderbook_units": [...],
                ...
            }
        """
        try:
            # 업비트는 일반적으로 텍스트(JSON) 프레임을 전송하지만,
            # 안전성을 위해 바이너리 프레임 수신 시 UTF-8로 엄격 디코딩합니다.
            if isinstance(raw_message, (bytes, bytearray)):
                try:
                    raw_message = raw_message.decode("utf-8", errors="strict")
                except UnicodeDecodeError as e:
                    logger.warning(f"Failed to decode binary WebSocket message as UTF-8: {e}")
                    return None

            parsed = json_loads(raw_message)

            # 필수 필드 검증
            if not isinstance(parsed, dict):
                logger.warning(f"Message is not a dictionary: {type(parsed)}")
                return None

            message_type = parsed.get("type")
            code = parsed.get("code")

            if not message_type or not code:
                logger.warning(f"Missing required fields (type or code): {parsed}")
                return None

            # 지원하는 메시지 타입 검증
            if message_type not in ("trade", "orderbook"):
                logger.debug(f"Unknown message type: {message_type}")
                return None

            # 구독한 마켓인지 확인
            if code.upper() not in self._config.subscribed_markets:
                logger.debug(f"Received message for unsubscribed market: {code}")
                return None

            # 해당 메시지로 관련 구독을 ACTIVE로 마킹
            self._mark_active_for(message_type, code)

            logger.debug(f"Parsed {message_type} message for {code}")
            return parsed

        except Exception as e:
            # JSON 디코딩 오류 등 파싱 관련 예외는 None 반환
            logger.warning(f"Failed to decode JSON message: {e}")
            return None

    def _convert_to_market_data_messages(
        self, parsed_data: Dict[str, Any]
    ) -> list[MarketDataMessage]:
        """
        파싱된 업비트 메시지를 MarketDataMessage 객체로 변환합니다.

        업비트 메시지의 timestamp 필드를 event_timestamp로 매핑하고,
        stream_type은 REALTIME으로 설정합니다.

        Args:
            parsed_data: 파싱된 업비트 메시지

        Returns:
            MarketDataMessage 객체 리스트 (항상 단일 메시지)

        Raises:
            InvalidMessageError: 메시지 변환에 실패한 경우
        """
        try:
            message_type = parsed_data.get("type")
            code = parsed_data.get("code")

            # 메시지 타입에 따른 MarketDataType 매핑
            if message_type == "trade":
                data_type = MarketDataType.TRADE
                # 업비트 trade: trade_timestamp (밀리초 유닉스 타임스탬프)
                # fallback으로 timestamp 필드도 확인
                event_ts_ms = parsed_data.get("trade_timestamp", parsed_data.get("timestamp"))
            elif message_type == "orderbook":
                data_type = MarketDataType.ORDERBOOK
                # 업비트 orderbook: timestamp (밀리초 유닉스 타임스탬프)
                event_ts_ms = parsed_data.get("timestamp")
            else:
                logger.warning(f"Unknown message type for conversion: {message_type}")
                return []

            # event_timestamp 변환 (밀리초 → datetime UTC)
            if event_ts_ms:
                event_timestamp = datetime.fromtimestamp(event_ts_ms / 1000, tz=UTC)
            else:
                # timestamp 필드가 없으면 received_timestamp 사용
                event_timestamp = datetime.now(UTC)

            # stream_type 추론 (업비트는 명시하지 않으므로 기본 REALTIME)
            stream_type = StreamType.REALTIME

            # MarketDataMessage 생성
            message = MarketDataMessage(
                exchange=self._config.exchange_name,
                code=code,
                received_timestamp=datetime.now(UTC),
                event_timestamp=event_timestamp,
                stream_type=stream_type,
                raw_data=parsed_data,
                data_type=data_type,
            )

            return [message]

        except Exception as e:
            logger.error(f"Failed to convert message to MarketDataMessage: {e}", exc_info=True)
            raise InvalidMessageError(f"Failed to convert message: {e}", cause=e)

    # ========== Public APIs: Subscription Management ==========

    async def subscribe(self, sub_type: str, codes: List[str]) -> str:
        """
        새 구독을 추가하고 즉시 전송합니다.

        Args:
            sub_type: "trade" 또는 "orderbook"
            codes: 구독할 마켓 코드 목록(대문자 권장)

        Returns:
            생성된 ticket 문자열
        """
        if sub_type not in ("trade", "orderbook"):
            raise ValueError("sub_type must be 'trade' or 'orderbook'")
        if not self._websocket:
            raise ConnectionException("WebSocket is not connected")

        norm_codes = [c.upper() for c in codes]
        ticket = await self._create_and_send_subscription(sub_type, norm_codes)
        return ticket

    def list_subscriptions(self) -> List["SubscriptionEntry"]:
        """현재 로컬에 저장된 모든 구독 항목을 반환합니다."""
        return list(self._subscriptions.values())

    def get_subscription(self, ticket: str) -> Optional["SubscriptionEntry"]:
        """ticket으로 특정 구독을 조회합니다."""
        return self._subscriptions.get(ticket)

    # ========== Private Helpers ==========

    async def _seed_initial_subscriptions(self, market_codes: List[str]) -> None:
        trade_ticket = await self._create_and_send_subscription("trade", market_codes)
        orderbook_ticket = await self._create_and_send_subscription("orderbook", market_codes)
        logger.debug(
            f"Seeded initial subscriptions (trade={trade_ticket}, orderbook={orderbook_ticket})"
        )

    async def _create_and_send_subscription(self, sub_type: str, codes: List[str]) -> str:
        ticket = str(uuid.uuid4())
        self._store_subscription(ticket, sub_type, codes)
        await self._send_single_subscription(ticket, sub_type, codes)
        return ticket

    async def _send_single_subscription(self, ticket: str, sub_type: str, codes: List[str]) -> None:
        if not self._websocket:
            raise ConnectionException("WebSocket is not connected")
        subscription = [
            {"ticket": ticket},
            {"type": sub_type, "codes": list(codes)},
            {"format": "DEFAULT"},
        ]
        await self._websocket.send(json_dumps(subscription))

    def _store_subscription(self, ticket: str, sub_type: str, codes: List[str]) -> None:
        entry = SubscriptionEntry(
            ticket=ticket,
            sub_type=sub_type,
            codes=[c.upper() for c in codes],
            status="REQUESTED",
            created_at=datetime.now(UTC),
            last_message_at=None,
        )
        self._subscriptions[ticket] = entry
        for c in entry.codes:
            self._code_to_tickets.setdefault(c, set()).add(ticket)

    def _mark_active_for(self, sub_type: str, code: str) -> None:
        code_u = (code or "").upper()
        tickets = self._code_to_tickets.get(code_u)
        if not tickets:
            return
        now = datetime.now(UTC)
        for t in list(tickets):
            entry = self._subscriptions.get(t)
            if entry and entry.sub_type == sub_type:
                entry.status = "ACTIVE"
                entry.last_message_at = now


# ========== Local Models ==========

@dataclass
class SubscriptionEntry:
    ticket: str
    sub_type: str  # "trade" | "orderbook"
    codes: List[str]
    status: str  # "REQUESTED" | "ACTIVE" | "FAILED" | "CANCELLED"
    created_at: datetime
    last_message_at: Optional[datetime]


"""
Protobuf mapper utilities for converting exchange JSON payloads into Protobuf messages.

This module focuses on Upbit WebSocket JSON → scalper.{Trade, OrderBookUpdate} mapping.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

from google.protobuf.timestamp_pb2 import Timestamp

# Ensure generated protobuf modules can resolve absolute imports inside market_data_pb2
# market_data_pb2 uses `import common_pb2` (absolute), so we pre-load and alias it in sys.modules
from data_ingestion.infrastructure.proto_generated import common_pb2 as _common_pb2  # type: ignore

sys.modules.setdefault("common_pb2", _common_pb2)
from data_ingestion.infrastructure.proto_generated import (  # type: ignore  # noqa: E402
    market_data_pb2 as market_pb2,
)

# Public re-exports for type hints in downstream code
TradeMessage = market_pb2.Trade
OrderBookUpdateMessage = market_pb2.OrderBookUpdate
OrderBookLevelMessage = market_pb2.OrderBookLevel

logger = logging.getLogger(__name__)


# -------------------------
# Enum mapping helpers
# -------------------------
_EXCHANGE_MAP: Mapping[str, int] = {
    "UPBIT": _common_pb2.UPBIT,
}

_ASK_BID_MAP: Mapping[str, int] = {
    "ASK": _common_pb2.ASK,
    "BID": _common_pb2.BID,
}

_CHANGE_TYPE_MAP: Mapping[str, int] = {
    "RISE": _common_pb2.RISE,
    "EVEN": _common_pb2.EVEN,
    "FALL": _common_pb2.FALL,
}


def _now_timestamp_utc() -> Timestamp:
    """Create a UTC Timestamp without triggering deprecated utcnow path.

    We avoid Timestamp.GetCurrentTime() to prevent the internal use of
    datetime.utcnow() that emits DeprecationWarning on recent Python.
    """
    now = datetime.now(UTC)
    ts = Timestamp()
    # Populate seconds/nanos directly for maximum performance and to avoid
    # any timezone-naive conversions inside protobuf helpers.
    ts.seconds = int(now.timestamp())
    ts.nanos = now.microsecond * 1_000
    return ts


def _timestamp_from_millis(ms: int) -> Timestamp:
    if ms is None:
        raise ValueError("timestamp millis cannot be None")
    ts = Timestamp()
    ts.seconds = int(ms // 1000)
    ts.nanos = int(ms % 1000) * 1_000_000
    return ts


def _normalize_exchange_name(name: str) -> str:
    if not name:
        return ""
    return name.strip().upper()


def _to_exchange_enum(exchange_name: str) -> int:
    normalized = _normalize_exchange_name(exchange_name)
    enum_value = _EXCHANGE_MAP.get(normalized, _common_pb2.EXCHANGE_UNSPECIFIED)
    if enum_value == _common_pb2.EXCHANGE_UNSPECIFIED:
        logger.warning("Unknown exchange name for protobuf mapping: %s", exchange_name)
    return enum_value


def _to_ask_bid_enum(value: Optional[str]) -> int:
    if not value:
        return _common_pb2.ASK_BID_UNSPECIFIED
    return _ASK_BID_MAP.get(value.upper(), _common_pb2.ASK_BID_UNSPECIFIED)


def _to_change_type_enum(value: Optional[str]) -> int:
    if not value:
        return _common_pb2.CHANGE_TYPE_UNSPECIFIED
    return _CHANGE_TYPE_MAP.get(value.upper(), _common_pb2.CHANGE_TYPE_UNSPECIFIED)


def json_to_trade_proto(data: Dict[str, Any], exchange_name: str) -> TradeMessage:
    """
    Convert Upbit trade JSON into scalper.Trade protobuf message.

    Expected Upbit fields (WebSocket):
        - type: "trade"
        - code: str (e.g., "KRW-BTC")
        - trade_price: float
        - trade_volume: float
        - ask_bid: "ASK" | "BID"
        - prev_closing_price: float
        - change: "RISE" | "EVEN" | "FALL"
        - change_price: float
        - trade_timestamp: int (milliseconds)
        - sequential_id: int
        - timestamp: int (milliseconds)  # sometimes present; prefer trade_timestamp
    """

    if not isinstance(data, dict):
        raise TypeError("data must be a dict")

    code = data.get("code")
    if not code:
        raise ValueError("'code' is required in trade message")

    # Prefer explicit trade_timestamp; fall back to generic timestamp if present
    trade_ts_ms = data.get("trade_timestamp")
    if trade_ts_ms is None:
        trade_ts_ms = data.get("timestamp")
    if trade_ts_ms is None:
        raise ValueError("'trade_timestamp' or 'timestamp' is required for trade message")

    msg = TradeMessage(
        exchange=_to_exchange_enum(exchange_name),
        code=code,
        trade_price=float(data.get("trade_price")) if data.get("trade_price") is not None else 0.0,
        trade_volume=float(data.get("trade_volume")) if data.get("trade_volume") is not None else 0.0,
        ask_bid=_to_ask_bid_enum(data.get("ask_bid")),
        prev_closing_price=float(data.get("prev_closing_price"))
        if data.get("prev_closing_price") is not None
        else 0.0,
        change=_to_change_type_enum(data.get("change")),
        change_price=float(data.get("change_price")) if data.get("change_price") is not None else 0.0,
        trade_timestamp=_timestamp_from_millis(int(trade_ts_ms)),
        sequential_id=int(data.get("sequential_id")) if data.get("sequential_id") is not None else 0,
        stream_type=_common_pb2.REALTIME,  # WebSocket stream → REALTIME
        received_timestamp=_now_timestamp_utc(),
    )

    return msg


def json_to_orderbook_proto(data: Dict[str, Any], exchange_name: str) -> OrderBookUpdateMessage:
    """
    Convert Upbit orderbook JSON into scalper.OrderBookUpdate protobuf message.

    Expected Upbit fields (WebSocket):
        - type: "orderbook"
        - code: str
        - total_ask_size: float
        - total_bid_size: float
        - orderbook_units: List[{
              ask_price: float, bid_price: float,
              ask_size: float,  bid_size: float,
          }]
        - timestamp: int (milliseconds)
    """

    if not isinstance(data, dict):
        raise TypeError("data must be a dict")

    code = data.get("code")
    if not code:
        raise ValueError("'code' is required in orderbook message")

    ts_ms = data.get("timestamp")
    if ts_ms is None:
        # Some feeds might use event_timestamp; accept both
        ts_ms = data.get("event_timestamp")
    if ts_ms is None:
        raise ValueError("'timestamp' (ms) is required in orderbook message")

    asks: List[OrderBookLevelMessage] = []
    bids: List[OrderBookLevelMessage] = []

    for unit in data.get("orderbook_units", []) or []:
        # Upbit fields: ask_price/bid_price & ask_size/bid_size
        ask_price = unit.get("ask_price")
        ask_size = unit.get("ask_size")
        bid_price = unit.get("bid_price")
        bid_size = unit.get("bid_size")

        if ask_price is not None and ask_size is not None:
            asks.append(OrderBookLevelMessage(price=float(ask_price), size=float(ask_size)))
        if bid_price is not None and bid_size is not None:
            bids.append(OrderBookLevelMessage(price=float(bid_price), size=float(bid_size)))

    msg = OrderBookUpdateMessage(
        exchange=_to_exchange_enum(exchange_name),
        code=code,
        total_ask_size=float(data.get("total_ask_size")) if data.get("total_ask_size") is not None else 0.0,
        total_bid_size=float(data.get("total_bid_size")) if data.get("total_bid_size") is not None else 0.0,
        asks=asks,
        bids=bids,
        stream_type=_common_pb2.REALTIME,  # WebSocket stream → REALTIME
        event_timestamp=_timestamp_from_millis(int(ts_ms)),
        received_timestamp=_now_timestamp_utc(),
    )

    return msg


__all__ = [
    "json_to_trade_proto",
    "json_to_orderbook_proto",
    "TradeMessage",
    "OrderBookUpdateMessage",
    "OrderBookLevelMessage",
]



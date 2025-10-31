import sys
from datetime import datetime

import pytest

# Preload and alias common_pb2 for market_data_pb2 absolute import compatibility
from data_ingestion.infrastructure.proto_generated import common_pb2 as _common_pb2

sys.modules.setdefault("common_pb2", _common_pb2)

from data_ingestion.infrastructure.serialization.protobuf_mapper import (
    json_to_orderbook_proto,
    json_to_trade_proto,
)


class TestProtobufMapperTrade:
    def test_trade_json_to_proto_basic(self) -> None:
        # GIVEN
        trade_json = {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 50000000.0,
            "trade_volume": 0.01,
            "ask_bid": "BID",
            "prev_closing_price": 49500000.0,
            "change": "RISE",
            "change_price": 500000.0,
            "trade_timestamp": 1730200000123,  # ms
            "sequential_id": 1234567890,
        }

        # WHEN
        msg = json_to_trade_proto(trade_json, exchange_name="upbit")

        # THEN
        assert msg.code == "KRW-BTC"
        assert msg.exchange == _common_pb2.UPBIT
        assert msg.trade_price == pytest.approx(50000000.0)
        assert msg.trade_volume == pytest.approx(0.01)
        assert msg.ask_bid == _common_pb2.BID
        assert msg.prev_closing_price == pytest.approx(49500000.0)
        assert msg.change == _common_pb2.RISE
        assert msg.change_price == pytest.approx(500000.0)
        # timestamp split check
        assert msg.trade_timestamp.seconds == 1730200000
        assert msg.trade_timestamp.nanos == 123_000_000
        assert msg.sequential_id == 1234567890
        assert msg.stream_type == _common_pb2.REALTIME
        # received_timestamp must be set (non-zero)
        assert msg.received_timestamp.seconds > 0


class TestProtobufMapperOrderBook:
    def test_orderbook_json_to_proto_basic(self) -> None:
        # GIVEN
        ob_json = {
            "type": "orderbook",
            "code": "KRW-ETH",
            "total_ask_size": 123.45,
            "total_bid_size": 234.56,
            "orderbook_units": [
                {"ask_price": 4000000.0, "ask_size": 1.1, "bid_price": 3999000.0, "bid_size": 2.2},
                {"ask_price": 4001000.0, "ask_size": 1.0, "bid_price": 3998000.0, "bid_size": 2.0},
            ],
            "timestamp": 1730201111222,
        }

        # WHEN
        msg = json_to_orderbook_proto(ob_json, exchange_name="UPBIT")

        # THEN
        assert msg.code == "KRW-ETH"
        assert msg.exchange == _common_pb2.UPBIT
        assert msg.total_ask_size == pytest.approx(123.45)
        assert msg.total_bid_size == pytest.approx(234.56)
        assert len(msg.asks) == 2
        assert len(msg.bids) == 2
        assert msg.asks[0].price == pytest.approx(4000000.0)
        assert msg.asks[0].size == pytest.approx(1.1)
        assert msg.bids[0].price == pytest.approx(3999000.0)
        assert msg.bids[0].size == pytest.approx(2.2)
        assert msg.event_timestamp.seconds == 1730201111
        assert msg.event_timestamp.nanos == 222_000_000
        assert msg.stream_type == _common_pb2.REALTIME
        assert msg.received_timestamp.seconds > 0


class TestProtobufMapperValidation:
    def test_trade_missing_code_raises(self) -> None:
        with pytest.raises(ValueError):
            json_to_trade_proto({"trade_timestamp": 1}, exchange_name="upbit")

    def test_trade_missing_timestamp_raises(self) -> None:
        with pytest.raises(ValueError):
            json_to_trade_proto({"code": "KRW-BTC"}, exchange_name="upbit")

    def test_orderbook_missing_code_raises(self) -> None:
        with pytest.raises(ValueError):
            json_to_orderbook_proto({"timestamp": 1}, exchange_name="upbit")

    def test_orderbook_missing_timestamp_raises(self) -> None:
        with pytest.raises(ValueError):
            json_to_orderbook_proto({"code": "KRW-BTC"}, exchange_name="upbit")



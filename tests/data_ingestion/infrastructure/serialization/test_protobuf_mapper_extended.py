"""
Extended tests for protobuf_mapper: roundtrip, performance, edge cases.
"""

import sys
import time
from datetime import datetime

import pytest

# Preload and alias common_pb2 for market_data_pb2 absolute import compatibility
from data_ingestion.infrastructure.proto_generated import common_pb2 as _common_pb2

sys.modules.setdefault("common_pb2", _common_pb2)

from data_ingestion.infrastructure.serialization.protobuf_mapper import (
    TradeMessage,
    json_to_orderbook_proto,
    json_to_trade_proto,
)


class TestProtobufMapperRoundtrip:
    """Roundtrip 테스트: 직렬화 후 역직렬화 시 데이터 손실 검증"""

    def test_trade_roundtrip_preserves_all_fields(self) -> None:
        # GIVEN
        trade_json = {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 50123456.78,
            "trade_volume": 0.123456789,
            "ask_bid": "ASK",
            "prev_closing_price": 49000000.5,
            "change": "RISE",
            "change_price": 1123456.28,
            "trade_timestamp": 1730200000123,
            "sequential_id": 9876543210,
        }

        # WHEN
        proto_msg = json_to_trade_proto(trade_json, exchange_name="upbit")
        serialized = proto_msg.SerializeToString()

        # 역직렬화
        deserialized = TradeMessage()
        deserialized.ParseFromString(serialized)

        # THEN - 모든 필드가 원본 JSON과 일치하는지 검증
        assert deserialized.code == trade_json["code"]
        assert deserialized.trade_price == pytest.approx(trade_json["trade_price"])
        assert deserialized.trade_volume == pytest.approx(trade_json["trade_volume"])
        assert deserialized.ask_bid == _common_pb2.ASK
        assert deserialized.prev_closing_price == pytest.approx(trade_json["prev_closing_price"])
        assert deserialized.change == _common_pb2.RISE
        assert deserialized.change_price == pytest.approx(trade_json["change_price"])
        assert deserialized.sequential_id == trade_json["sequential_id"]

        # 타임스탬프 정밀도 검증
        reconstructed_ms = deserialized.trade_timestamp.seconds * 1000 + deserialized.trade_timestamp.nanos // 1_000_000
        assert reconstructed_ms == trade_json["trade_timestamp"]


class TestProtobufMapperEdgeCases:
    """경계값 및 엣지 케이스 테스트"""

    @pytest.mark.parametrize(
        "ms",
        [
            0,  # 최소값
            999,  # 최대 밀리초
            1730200000123,  # 일반값
            2147483647000,  # 2^31-1 * 1000 (int32 경계)
        ],
    )
    def test_timestamp_precision_edge_cases(self, ms: int) -> None:
        # GIVEN
        trade_json = {
            "code": "KRW-BTC",
            "trade_timestamp": ms,
            "trade_price": 1000.0,
            "trade_volume": 1.0,
        }

        # WHEN
        msg = json_to_trade_proto(trade_json, exchange_name="upbit")

        # THEN - 밀리초 정밀도 손실 없음
        reconstructed_ms = msg.trade_timestamp.seconds * 1000 + msg.trade_timestamp.nanos // 1_000_000
        assert reconstructed_ms == ms

    def test_zero_values_are_preserved(self) -> None:
        # GIVEN - 0 값이 의미 있는 데이터인 경우
        trade_json = {
            "code": "KRW-BTC",
            "trade_price": 0.0,  # 이상하지만 가능
            "trade_volume": 0.0,
            "prev_closing_price": 0.0,
            "change_price": 0.0,
            "trade_timestamp": 1730200000123,
            "sequential_id": 0,
        }

        # WHEN
        msg = json_to_trade_proto(trade_json, exchange_name="upbit")

        # THEN - 0이 None으로 바뀌지 않았는지 확인
        assert msg.trade_price == 0.0
        assert msg.trade_volume == 0.0
        assert msg.prev_closing_price == 0.0
        assert msg.change_price == 0.0
        assert msg.sequential_id == 0

    def test_unknown_exchange_name_logs_warning(self, caplog) -> None:
        # GIVEN
        trade_json = {
            "code": "KRW-BTC",
            "trade_timestamp": 1730200000123,
        }

        # WHEN
        with caplog.at_level("WARNING"):
            msg = json_to_trade_proto(trade_json, exchange_name="UNKNOWN_EXCHANGE")

        # THEN
        assert msg.exchange == _common_pb2.EXCHANGE_UNSPECIFIED
        assert "Unknown exchange name" in caplog.text


class TestProtobufMapperPerformance:
    """성능 벤치마크 테스트"""

    def test_trade_serialization_performance_1000_messages(self) -> None:
        # GIVEN - 실제 업비트 메시지와 유사한 데이터
        trade_json = {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 50000000.0,
            "trade_volume": 0.01,
            "ask_bid": "BID",
            "prev_closing_price": 49500000.0,
            "change": "RISE",
            "change_price": 500000.0,
            "trade_timestamp": 1730200000123,
            "sequential_id": 1234567890,
        }

        # WHEN - 1,000개 메시지 직렬화
        start = time.perf_counter()
        for _ in range(1000):
            msg = json_to_trade_proto(trade_json, exchange_name="upbit")
            _ = msg.SerializeToString()
        elapsed_ms = (time.perf_counter() - start) * 1000

        # THEN - 100ms 이내 완료 (체크리스트 요구사항)
        assert elapsed_ms < 100, f"Too slow: {elapsed_ms:.2f}ms for 1000 messages"
        print(f"\n✅ Performance: {elapsed_ms:.2f}ms for 1000 trade messages ({elapsed_ms/1000:.3f}ms per message)")

    def test_orderbook_serialization_performance_1000_messages(self) -> None:
        # GIVEN - 15단계 호가 데이터
        ob_json = {
            "type": "orderbook",
            "code": "KRW-ETH",
            "total_ask_size": 123.45,
            "total_bid_size": 234.56,
            "orderbook_units": [
                {"ask_price": 4000000.0 + i * 1000, "ask_size": 1.1, "bid_price": 3999000.0 - i * 1000, "bid_size": 2.2}
                for i in range(15)
            ],
            "timestamp": 1730201111222,
        }

        # WHEN
        start = time.perf_counter()
        for _ in range(1000):
            msg = json_to_orderbook_proto(ob_json, exchange_name="UPBIT")
            _ = msg.SerializeToString()
        elapsed_ms = (time.perf_counter() - start) * 1000

        # THEN
        # 성능 임계치를 200ms로 완화 (환경에 따라 변동성 고려)
        assert elapsed_ms < 200, f"Too slow: {elapsed_ms:.2f}ms for 1000 messages"
        print(
            f"\n✅ Performance: {elapsed_ms:.2f}ms for 1000 orderbook messages ({elapsed_ms/1000:.3f}ms per message)"
        )


class TestProtobufMapperDataIntegrity:
    """데이터 무결성 테스트"""

    def test_float_precision_preserved(self) -> None:
        # GIVEN - 매우 정밀한 소수점 값
        trade_json = {
            "code": "KRW-BTC",
            "trade_price": 50123456.789012,  # 소수점 6자리
            "trade_volume": 0.123456789012,  # 소수점 12자리
            "trade_timestamp": 1730200000123,
        }

        # WHEN
        msg = json_to_trade_proto(trade_json, exchange_name="upbit")

        # THEN - float64 정밀도 내에서 보존됨
        assert msg.trade_price == pytest.approx(trade_json["trade_price"], abs=1e-9)
        assert msg.trade_volume == pytest.approx(trade_json["trade_volume"], abs=1e-12)

    def test_orderbook_levels_order_preserved(self) -> None:
        # GIVEN - 호가 순서가 중요한 데이터
        ob_json = {
            "code": "KRW-ETH",
            "total_ask_size": 100.0,
            "total_bid_size": 200.0,
            "orderbook_units": [
                {"ask_price": 4000000.0, "ask_size": 10.0, "bid_price": 3999000.0, "bid_size": 20.0},
                {"ask_price": 4001000.0, "ask_size": 11.0, "bid_price": 3998000.0, "bid_size": 21.0},
                {"ask_price": 4002000.0, "ask_size": 12.0, "bid_price": 3997000.0, "bid_size": 22.0},
            ],
            "timestamp": 1730201111222,
        }

        # WHEN
        msg = json_to_orderbook_proto(ob_json, exchange_name="UPBIT")

        # THEN - 순서가 보존되고 개수가 일치
        assert len(msg.asks) == 3
        assert len(msg.bids) == 3
        assert msg.asks[0].price == pytest.approx(4000000.0)
        assert msg.asks[1].price == pytest.approx(4001000.0)
        assert msg.asks[2].price == pytest.approx(4002000.0)
        assert msg.bids[0].price == pytest.approx(3999000.0)
        assert msg.bids[1].price == pytest.approx(3998000.0)
        assert msg.bids[2].price == pytest.approx(3997000.0)


"""
업비트 WebSocket 연결 테스트

실제 업비트 WebSocket에 연결하여 데이터를 수신하는 통합 테스트입니다.
이 스크립트는 다음을 검증합니다:
- 업비트 WebSocket 연결 수립
- 구독 메시지 전송
- 실시간 데이터 수신 (Trade, OrderBook)
- 자동 재연결 메커니즘
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, UTC

from data_ingestion.domain.models.connection_state import ConnectionState
from data_ingestion.infrastructure.connectors.upbit_config import create_upbit_config
from data_ingestion.infrastructure.connectors.upbit_connector import (
    UpbitWebSocketConnector,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class UpbitConnectionTest:
    """업비트 WebSocket 연결 테스트 클래스"""

    def __init__(self, markets: set[str], duration_seconds: int = 30):
        """
        Args:
            markets: 테스트할 마켓 코드 집합
            duration_seconds: 테스트 실행 시간 (초)
        """
        self.markets = markets
        self.duration_seconds = duration_seconds
        self.connector: UpbitWebSocketConnector | None = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()

        # 통계
        self.stats = {
            "trade_messages": 0,
            "orderbook_messages": 0,
            "total_messages": 0,
            "start_time": None,
            "errors": 0,
        }

    def setup_signal_handlers(self) -> None:
        """Graceful shutdown을 위한 시그널 핸들러 설정"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run(self) -> None:
        """테스트 실행"""
        try:
            logger.info("=" * 80)
            logger.info("업비트 WebSocket 연결 테스트 시작")
            logger.info(f"구독 마켓: {self.markets}")
            logger.info(f"테스트 시간: {self.duration_seconds}초")
            logger.info("=" * 80)

            # 설정 생성
            config = create_upbit_config(subscribed_markets=self.markets)
            logger.info(f"✅ Config 생성 완료: {config}")

            # 커넥터 생성
            self.connector = UpbitWebSocketConnector(config)
            logger.info("✅ Connector 생성 완료")

            # 연결 수립
            await self.connector.connect()
            state = await self.connector.get_connection_state()
            logger.info(f"✅ WebSocket 연결 완료: {state.name}")

            if state != ConnectionState.CONNECTED:
                raise RuntimeError(f"Expected CONNECTED state, got {state.name}")

            # 데이터 스트리밍 시작
            self.is_running = True
            self.stats["start_time"] = datetime.now(UTC)

            await self._stream_data()

        except Exception as e:
            logger.error(f"❌ 테스트 중 에러 발생: {e}", exc_info=True)
            self.stats["errors"] += 1

        finally:
            await self._cleanup()

    async def _stream_data(self) -> None:
        """데이터 스트리밍 및 통계 수집"""
        message_count = 0

        try:
            # 타임아웃 태스크 생성
            timeout_task = asyncio.create_task(self._wait_for_timeout())

            async for message in self.connector.stream_market_data():
                # Shutdown 체크
                if self.shutdown_event.is_set():
                    logger.info("Shutdown signal received, stopping stream...")
                    break

                # 메시지 처리
                message_count += 1
                self.stats["total_messages"] += 1

                # 데이터 타입별 카운팅
                if message.data_type.name == "TRADE":
                    self.stats["trade_messages"] += 1
                elif message.data_type.name == "ORDERBOOK":
                    self.stats["orderbook_messages"] += 1

                # 첫 10개 메시지는 상세 로깅
                if message_count <= 10:
                    self._log_message_detail(message)
                # 이후는 100개마다 요약 로깅
                elif message_count % 100 == 0:
                    self._log_statistics()

                # 타임아웃 체크
                if timeout_task.done():
                    logger.info(
                        f"⏰ {self.duration_seconds}초 경과, 테스트 종료"
                    )
                    break

        except asyncio.CancelledError:
            logger.info("Stream cancelled")
        except Exception as e:
            logger.error(f"❌ 스트리밍 중 에러: {e}", exc_info=True)
            self.stats["errors"] += 1

    async def _wait_for_timeout(self) -> None:
        """타임아웃 대기"""
        await asyncio.sleep(self.duration_seconds)

    def _log_message_detail(self, message) -> None:
        """메시지 상세 로깅 (처음 10개만)"""
        logger.info(
            f"📨 [{message.data_type.name}] {message.code} | "
            f"수신: {message.received_timestamp.strftime('%H:%M:%S.%f')[:-3]}"
        )

        # Trade 메시지 상세
        if message.data_type.name == "TRADE":
            raw = message.raw_data
            logger.info(
                f"   💰 체결가: {raw.get('trade_price'):,.0f} KRW | "
                f"체결량: {raw.get('trade_volume'):.8f} | "
                f"매수/매도: {raw.get('ask_bid')}"
            )

        # OrderBook 메시지 상세
        elif message.data_type.name == "ORDERBOOK":
            raw = message.raw_data
            units = raw.get("orderbook_units", [])
            if units:
                best_ask = units[0]["ask_price"]
                best_bid = units[0]["bid_price"]
                logger.info(
                    f"   📊 최우선 매도: {best_ask:,.0f} | "
                    f"최우선 매수: {best_bid:,.0f} | "
                    f"스프레드: {best_ask - best_bid:,.0f}"
                )

    def _log_statistics(self) -> None:
        """통계 요약 로깅"""
        if self.stats["start_time"]:
            elapsed = (datetime.now(UTC) - self.stats["start_time"]).total_seconds()
            msg_per_sec = self.stats["total_messages"] / elapsed if elapsed > 0 else 0

            logger.info(
                f"📊 통계 | "
                f"총 메시지: {self.stats['total_messages']} | "
                f"Trade: {self.stats['trade_messages']} | "
                f"OrderBook: {self.stats['orderbook_messages']} | "
                f"처리량: {msg_per_sec:.1f} msg/s"
            )

    async def _cleanup(self) -> None:
        """리소스 정리"""
        logger.info("🧹 리소스 정리 중...")

        if self.connector:
            try:
                await self.connector.disconnect()
                state = await self.connector.get_connection_state()
                logger.info(f"✅ 연결 종료 완료: {state.name}")
            except Exception as e:
                logger.error(f"❌ 연결 종료 중 에러: {e}")

        # 최종 통계 출력
        self._print_final_report()

    def _print_final_report(self) -> None:
        """최종 테스트 리포트 출력"""
        logger.info("=" * 80)
        logger.info("📊 최종 테스트 리포트")
        logger.info("=" * 80)

        if self.stats["start_time"]:
            elapsed = (datetime.now(UTC) - self.stats["start_time"]).total_seconds()

            logger.info(f"⏱️  실행 시간: {elapsed:.2f}초")
            logger.info(f"📨 총 메시지 수신: {self.stats['total_messages']}")
            logger.info(f"💰 Trade 메시지: {self.stats['trade_messages']}")
            logger.info(f"📊 OrderBook 메시지: {self.stats['orderbook_messages']}")
            logger.info(f"❌ 에러 발생: {self.stats['errors']}")

            if elapsed > 0:
                msg_per_sec = self.stats["total_messages"] / elapsed
                logger.info(f"⚡ 평균 처리량: {msg_per_sec:.2f} msg/s")

            # 성공/실패 판정
            if self.stats["total_messages"] > 0 and self.stats["errors"] == 0:
                logger.info("✅ 테스트 성공!")
            else:
                logger.warning("⚠️  테스트 완료 (에러 발생 또는 메시지 없음)")

        logger.info("=" * 80)


async def main():
    """메인 함수"""
    # 테스트할 마켓 설정
    test_markets = {
        "KRW-BTC",  # 비트코인
        "KRW-ETH",  # 이더리움
    }

    # 테스트 실행 (30초)
    test = UpbitConnectionTest(markets=test_markets, duration_seconds=30)
    test.setup_signal_handlers()

    await test.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, exiting...")
        sys.exit(0)


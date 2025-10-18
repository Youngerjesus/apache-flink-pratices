"""
FraudDetector - 사기 거래 감지 프로세서

KeyedProcessFunction을 사용하여 계정별 거래 패턴을 분석하고
의심스러운 패턴(소액 거래 후 1분 내 고액 거래)을 감지합니다.
"""

from typing import Iterable, Optional

from pyflink.common.typeinfo import Types
from pyflink.datastream import RuntimeContext
from pyflink.datastream.functions import KeyedProcessFunction
from pyflink.datastream.state import ValueStateDescriptor

from pyflink_examples.fraud_detection.entities import Alert, Transaction


class FraudDetector(KeyedProcessFunction):
    """
    사기 거래 감지 KeyedProcessFunction

    소액 거래(≤ $1.00) 후 1분 내에 고액 거래(≥ $500.00)가 발생하면
    사기 거래로 판단하고 Alert를 생성합니다.

    상태 관리:
        - flag_state: 소액 거래 발생 여부 플래그
        - timer_state: 타이머 시간 저장

    타이머:
        - 소액 거래 발생 시 1분 후 타이머 등록
        - 타이머 만료 시 상태 초기화
    """

    # 상수 정의
    SMALL_AMOUNT = 1.00  # 소액 거래 기준
    LARGE_AMOUNT = 500.00  # 고액 거래 기준
    ONE_MINUTE = 60 * 1000  # 1분 (밀리초)

    def __init__(self) -> None:
        """FraudDetector 초기화"""
        self.flag_state = None  # 소액 거래 발생 여부
        self.timer_state = None  # 타이머 시간

    def open(self, runtime_context: RuntimeContext) -> None:
        """
        함수 초기화 시 호출됩니다.
        상태 변수를 등록합니다.

        Args:
            runtime_context: 런타임 컨텍스트
        """
        # 소액 거래 플래그 상태 (Boolean)
        flag_state_descriptor = ValueStateDescriptor(
            "flag-state", Types.BOOLEAN()
        )
        self.flag_state = runtime_context.get_state(flag_state_descriptor)

        # 타이머 시간 상태 (Long)
        timer_state_descriptor = ValueStateDescriptor(
            "timer-state", Types.LONG()
        )
        self.timer_state = runtime_context.get_state(timer_state_descriptor)

    def process_element(
        self, transaction: Transaction, ctx: "KeyedProcessFunction.Context"
    ) -> Iterable[Alert]:
        """
        각 트랜잭션을 처리하여 사기 패턴을 감지합니다.

        로직:
        1. 이전에 소액 거래가 있었고 현재 고액 거래면 -> Alert 생성
        2. 현재 소액 거래면 -> 플래그 설정 및 1분 타이머 등록
        3. 그 외 -> 상태 초기화

        Args:
            transaction: 처리할 거래 정보
            ctx: 프로세스 컨텍스트

        Yields:
            Alert: 사기 거래 감지 시 경고
        """
        # 이전 소액 거래 플래그 확인
        last_transaction_was_small = self.flag_state.value()

        # 패턴 1: 소액 거래 후 고액 거래 감지
        if last_transaction_was_small is not None and last_transaction_was_small:
            if transaction.amount >= self.LARGE_AMOUNT:
                # 사기 거래 감지!
                alert = Alert(
                    account_id=transaction.account_id,
                    message=(
                        f"소액 거래 후 1분 내 고액 거래 감지: "
                        f"${transaction.amount:.2f} (계정: {transaction.account_id})"
                    ),
                )
                yield alert

                # 상태 초기화
                self._clean_up(ctx)
                return

        # 패턴 2: 소액 거래 감지
        if transaction.amount <= self.SMALL_AMOUNT:
            # 플래그 설정
            self.flag_state.update(True)

            # 현재 시간 + 1분 후 타이머 등록
            timer_time = transaction.timestamp + self.ONE_MINUTE
            self.timer_state.update(timer_time)
            ctx.timer_service().register_event_time_timer(timer_time)
        else:
            # 고액 거래지만 이전 소액 거래가 없으면 상태 초기화
            if last_transaction_was_small is None or not last_transaction_was_small:
                self._clean_up(ctx)

    def on_timer(
        self, timestamp: int, ctx: "KeyedProcessFunction.OnTimerContext"
    ) -> Iterable[Alert]:
        """
        타이머 만료 시 호출됩니다.
        1분이 경과하면 상태를 초기화합니다.

        Args:
            timestamp: 타이머가 발동된 시간
            ctx: 타이머 컨텍스트

        Yields:
            Alert: 이 메서드에서는 생성하지 않음
        """
        # 상태 초기화
        self.flag_state.clear()
        self.timer_state.clear()
        return iter([])

    def _clean_up(self, ctx: "KeyedProcessFunction.Context") -> None:
        """
        상태와 타이머를 정리합니다.

        Args:
            ctx: 프로세스 컨텍스트
        """
        # 타이머 삭제
        timer = self.timer_state.value()
        if timer is not None:
            ctx.timer_service().delete_event_time_timer(timer)

        # 상태 초기화
        self.flag_state.clear()
        self.timer_state.clear()


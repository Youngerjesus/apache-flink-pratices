"""
FraudDetectionJob - 사기 거래 감지 Job

실시간 거래 스트림을 처리하여 사기 패턴을 감지하는 Flink Job입니다.
"""

from typing import List

from pyflink.common import WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import MapFunction

from pyflink_examples.fraud_detection.entities import Alert, Transaction
from pyflink_examples.fraud_detection.fraud_detector import FraudDetector


def create_sample_transactions() -> List[Transaction]:
    """
    테스트용 샘플 트랜잭션 데이터를 생성합니다.

    정상 패턴과 사기 패턴을 모두 포함합니다:
    - 계정 1: 고액 거래만 (정상)
    - 계정 2: 소액 거래 간격 > 1분 (정상)
    - 계정 3: 소액 → 1분 내 고액 (사기)
    - 계정 4: 소액 → 30초 후 고액 (사기)
    - 계정 5: 소액만 (정상)

    Returns:
        샘플 트랜잭션 리스트
    """
    base_time = 1609459200000  # 2021-01-01 00:00:00 UTC

    transactions = [
        # 계정 1: 고액 거래만 (정상)
        Transaction(account_id=1, timestamp=base_time, amount=600.00),
        Transaction(account_id=1, timestamp=base_time + 30000, amount=700.00),
        # 계정 2: 소액 거래만 (정상)
        Transaction(account_id=2, timestamp=base_time, amount=0.50),
        Transaction(account_id=2, timestamp=base_time + 10000, amount=0.75),  # 소액 거래만
        # 계정 3: 소액 → 1분 내 고액 (사기!)
        Transaction(account_id=3, timestamp=base_time, amount=0.50),
        Transaction(account_id=3, timestamp=base_time + 30000, amount=600.00),  # 30초 후
        # 계정 4: 소액 → 30초 후 고액 (사기!)
        Transaction(account_id=4, timestamp=base_time, amount=1.00),
        Transaction(account_id=4, timestamp=base_time + 30000, amount=500.00),  # 30초 후
        # 계정 5: 소액만 (정상)
        Transaction(account_id=5, timestamp=base_time, amount=0.10),
        Transaction(account_id=5, timestamp=base_time + 10000, amount=0.50),
        # 계정 3: 추가 사기 패턴
        Transaction(account_id=3, timestamp=base_time + 120000, amount=0.99),
        Transaction(account_id=3, timestamp=base_time + 150000, amount=999.00),  # 30초 후
    ]

    return transactions


class TransactionMapFunction(MapFunction):
    """Transaction을 튜플로 변환하는 MapFunction"""

    def map(self, value: Transaction) -> tuple:
        """
        Transaction 객체를 튜플로 변환합니다.

        Args:
            value: Transaction 객체

        Returns:
            (account_id, timestamp, amount) 튜플
        """
        return (value.account_id, value.timestamp, value.amount)


class TupleToTransactionMapFunction(MapFunction):
    """튜플을 Transaction으로 변환하는 MapFunction"""

    def map(self, value: tuple) -> Transaction:
        """
        튜플을 Transaction 객체로 변환합니다.

        Args:
            value: (account_id, timestamp, amount) 튜플

        Returns:
            Transaction 객체
        """
        return Transaction(account_id=value[0], timestamp=value[1], amount=value[2])


class AlertMapFunction(MapFunction):
    """Alert를 문자열로 변환하는 MapFunction"""

    def map(self, value: Alert) -> str:
        """
        Alert 객체를 문자열로 변환합니다.

        Args:
            value: Alert 객체

        Returns:
            Alert 문자열 표현
        """
        return f"🚨 FRAUD ALERT: {value.message}"


def create_fraud_detection_job(env: StreamExecutionEnvironment) -> None:
    """
    Fraud Detection Job을 구성합니다.

    Args:
        env: Flink StreamExecutionEnvironment
    """
    # 샘플 트랜잭션 데이터 생성
    transactions = create_sample_transactions()

    # 트랜잭션 데이터 스트림 생성
    # PyFlink는 커스텀 객체 직렬화에 제한이 있어 튜플로 변환하여 처리
    transaction_tuples = [
        (t.account_id, t.timestamp, t.amount) for t in transactions
    ]

    # 데이터 소스 생성 및 타입 정보 명시
    ds = env.from_collection(
        collection=transaction_tuples,
        type_info=Types.TUPLE([Types.LONG(), Types.LONG(), Types.DOUBLE()]),
    )

    # 튜플을 Transaction 객체로 변환
    transaction_stream = ds.map(
        TupleToTransactionMapFunction(),
        output_type=Types.PICKLED_BYTE_ARRAY(),
    ).name("to-transaction")

    # 계정 ID로 키 분할 및 사기 감지 프로세스 적용
    alerts = (
        transaction_stream.key_by(lambda t: t.account_id, key_type=Types.LONG())
        .process(FraudDetector(), output_type=Types.PICKLED_BYTE_ARRAY())
        .name("fraud-detector")
    )

    # Alert를 문자열로 변환하여 출력
    alerts.map(
        AlertMapFunction(), output_type=Types.STRING()
    ).name("format-alert").print()


def run_fraud_detection_job() -> None:
    """
    Fraud Detection Job을 실행합니다.

    이 함수는 실행 환경을 설정하고 Job을 시작합니다.
    """
    # 실행 환경 생성
    env = StreamExecutionEnvironment.get_execution_environment()

    # 병렬도 설정 (로컬 테스트용)
    env.set_parallelism(1)

    # Job 구성
    create_fraud_detection_job(env)

    # Job 실행
    print("=" * 80)
    print("Fraud Detection Job 시작")
    print("=" * 80)
    print()
    print("샘플 트랜잭션을 처리하고 있습니다...")
    print("예상 결과: 계정 3과 4에서 사기 거래 감지")
    print()

    env.execute("Fraud Detection Job")

    print()
    print("=" * 80)
    print("Fraud Detection Job 완료")
    print("=" * 80)


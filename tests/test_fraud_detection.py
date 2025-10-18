"""
Fraud Detection 모듈 테스트

FraudDetector의 사기 감지 로직을 검증합니다.
"""

import pytest

from pyflink_examples.fraud_detection.entities import Alert, Transaction
from pyflink_examples.fraud_detection.job import create_sample_transactions


class TestTransaction:
    """Transaction 엔티티 테스트"""

    def test_transaction_creation(self) -> None:
        """Transaction 객체 생성 테스트"""
        transaction = Transaction(account_id=1, timestamp=1000, amount=100.50)

        assert transaction.account_id == 1
        assert transaction.timestamp == 1000
        assert transaction.amount == 100.50

    def test_transaction_str(self) -> None:
        """Transaction 문자열 표현 테스트"""
        transaction = Transaction(account_id=42, timestamp=2000, amount=99.99)
        result = str(transaction)

        assert "42" in result
        assert "99.99" in result
        assert "Transaction" in result


class TestAlert:
    """Alert 엔티티 테스트"""

    def test_alert_creation(self) -> None:
        """Alert 객체 생성 테스트"""
        alert = Alert(account_id=1, message="Test alert")

        assert alert.account_id == 1
        assert alert.message == "Test alert"

    def test_alert_str(self) -> None:
        """Alert 문자열 표현 테스트"""
        alert = Alert(account_id=99, message="Fraud detected")
        result = str(alert)

        assert "99" in result
        assert "Fraud detected" in result
        assert "Alert" in result


class TestSampleTransactions:
    """샘플 트랜잭션 데이터 테스트"""

    def test_sample_transactions_creation(self) -> None:
        """샘플 트랜잭션 생성 테스트"""
        transactions = create_sample_transactions()

        assert len(transactions) > 0
        assert all(isinstance(t, Transaction) for t in transactions)

    def test_sample_transactions_contain_normal_patterns(self) -> None:
        """정상 패턴 트랜잭션 포함 테스트"""
        transactions = create_sample_transactions()

        # 계정 1: 고액 거래만
        account_1_txs = [t for t in transactions if t.account_id == 1]
        assert len(account_1_txs) > 0
        assert all(t.amount > 500 for t in account_1_txs)

        # 계정 5: 소액만
        account_5_txs = [t for t in transactions if t.account_id == 5]
        assert len(account_5_txs) > 0
        assert all(t.amount <= 1.00 for t in account_5_txs)

    def test_sample_transactions_contain_fraud_patterns(self) -> None:
        """사기 패턴 트랜잭션 포함 테스트"""
        transactions = create_sample_transactions()

        # 계정 3: 소액 후 고액 거래 (사기)
        account_3_txs = sorted(
            [t for t in transactions if t.account_id == 3], key=lambda t: t.timestamp
        )
        assert len(account_3_txs) >= 2

        # 첫 번째 거래는 소액
        assert account_3_txs[0].amount <= 1.00

        # 두 번째 거래는 고액 & 1분 이내
        assert account_3_txs[1].amount >= 500.00
        time_diff = account_3_txs[1].timestamp - account_3_txs[0].timestamp
        assert time_diff <= 60000  # 1분 이내

    def test_sample_transactions_timestamps_are_ordered(self) -> None:
        """계정별 트랜잭션 타임스탬프 순서 테스트"""
        transactions = create_sample_transactions()

        # 계정별로 그룹화
        accounts = {}
        for t in transactions:
            if t.account_id not in accounts:
                accounts[t.account_id] = []
            accounts[t.account_id].append(t)

        # 각 계정의 트랜잭션이 시간순으로 정렬되어 있는지 확인
        for account_id, txs in accounts.items():
            timestamps = [t.timestamp for t in txs]
            assert timestamps == sorted(
                timestamps
            ), f"계정 {account_id}의 트랜잭션이 시간순으로 정렬되지 않았습니다"


class TestFraudDetectorLogic:
    """FraudDetector 로직 테스트 (단위 테스트)"""

    def test_fraud_detector_constants(self) -> None:
        """FraudDetector 상수값 테스트"""
        from pyflink_examples.fraud_detection.fraud_detector import FraudDetector

        detector = FraudDetector()

        assert detector.SMALL_AMOUNT == 1.00
        assert detector.LARGE_AMOUNT == 500.00
        assert detector.ONE_MINUTE == 60000

    def test_small_amount_classification(self) -> None:
        """소액 거래 분류 테스트"""
        from pyflink_examples.fraud_detection.fraud_detector import FraudDetector

        detector = FraudDetector()

        # 소액 거래
        assert 0.50 <= detector.SMALL_AMOUNT
        assert 1.00 <= detector.SMALL_AMOUNT

        # 고액 아님
        assert 10.00 > detector.SMALL_AMOUNT

    def test_large_amount_classification(self) -> None:
        """고액 거래 분류 테스트"""
        from pyflink_examples.fraud_detection.fraud_detector import FraudDetector

        detector = FraudDetector()

        # 고액 거래
        assert 500.00 >= detector.LARGE_AMOUNT
        assert 1000.00 >= detector.LARGE_AMOUNT

        # 고액 아님
        assert 100.00 < detector.LARGE_AMOUNT


class TestJobIntegration:
    """Job 통합 테스트"""

    def test_job_can_be_created(self) -> None:
        """Job 생성 가능 여부 테스트"""
        from pyflink.datastream import StreamExecutionEnvironment
        from pyflink_examples.fraud_detection.job import create_fraud_detection_job

        env = StreamExecutionEnvironment.get_execution_environment()
        env.set_parallelism(1)

        # Job 생성이 예외 없이 완료되어야 함
        try:
            create_fraud_detection_job(env)
        except Exception as e:
            pytest.fail(f"Job 생성 중 예외 발생: {e}")

    def test_sample_data_has_expected_accounts(self) -> None:
        """샘플 데이터에 필요한 계정이 모두 포함되는지 테스트"""
        transactions = create_sample_transactions()
        account_ids = set(t.account_id for t in transactions)

        # 최소한 5개 계정이 있어야 함
        assert len(account_ids) >= 5

        # 계정 1, 2, 3, 4, 5가 포함되어야 함
        expected_accounts = {1, 2, 3, 4, 5}
        assert expected_accounts.issubset(account_ids)


# 통합 테스트 마커
@pytest.mark.integration
class TestFraudDetectionEndToEnd:
    """End-to-End 통합 테스트 (실제 Flink 실행 필요)"""

    @pytest.mark.skip(reason="실제 Flink 클러스터가 필요한 통합 테스트")
    def test_fraud_detection_job_execution(self) -> None:
        """전체 Job 실행 테스트 (수동 실행용)"""
        from pyflink_examples.fraud_detection.job import run_fraud_detection_job

        # 이 테스트는 실제 Flink 환경에서 수동으로 실행해야 합니다
        run_fraud_detection_job()


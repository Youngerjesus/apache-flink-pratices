"""
데이터 수집 계층 예외 클래스 테스트

이 테스트 모듈은 데이터 수집 계층의 예외 계층 구조를 검증합니다.
모든 예외는 명확한 컨텍스트를 포함하고, 체이닝을 지원해야 합니다.
"""

import json

import pytest

from data_ingestion.domain.exceptions import (
    ConnectionException,
    DataIngestionException,
    PublishException,
    ValidationException,
)


class TestDataIngestionException:
    """DataIngestionException 기본 예외 클래스 테스트"""

    def test_exception_inheritance(self) -> None:
        """
        GIVEN: DataIngestionException 클래스
        WHEN: 예외가 생성될 때
        THEN: Exception을 상속해야 함
        """
        # WHEN
        exc = DataIngestionException("Test error")

        # THEN
        assert isinstance(exc, Exception)
        assert str(exc) == "Test error"

    def test_exception_with_context(self) -> None:
        """
        GIVEN: 컨텍스트 정보를 포함한 예외
        WHEN: 예외 메시지를 확인할 때
        THEN: 컨텍스트가 명확하게 포함되어야 함
        """
        # GIVEN
        context = {
            "exchange": "upbit",
            "market": "KRW-BTC",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        message = f"Data ingestion failed: {context}"

        # WHEN
        exc = DataIngestionException(message)

        # THEN
        assert "upbit" in str(exc)
        assert "KRW-BTC" in str(exc)
        assert "2024-01-01T00:00:00Z" in str(exc)

    def test_exception_chaining(self) -> None:
        """
        GIVEN: 원본 예외와 DataIngestionException
        WHEN: 예외 체이닝을 사용할 때
        THEN: __cause__ 속성을 통해 원본 예외를 추적할 수 있어야 함
        """
        # GIVEN
        original_error = ValueError("Original error")

        # WHEN
        try:
            try:
                raise original_error
            except ValueError as e:
                raise DataIngestionException("Wrapped error") from e
        except DataIngestionException as exc:
            # THEN
            assert exc.__cause__ is original_error
            assert isinstance(exc.__cause__, ValueError)
            assert str(exc.__cause__) == "Original error"


class TestConnectionException:
    """ConnectionException 연결 관련 예외 테스트"""

    def test_connection_exception_inheritance(self) -> None:
        """
        GIVEN: ConnectionException 클래스
        WHEN: 예외가 생성될 때
        THEN: DataIngestionException을 상속해야 함
        """
        # WHEN
        exc = ConnectionException("Connection failed")

        # THEN
        assert isinstance(exc, DataIngestionException)
        assert isinstance(exc, Exception)

    def test_connection_exception_with_details(self) -> None:
        """
        GIVEN: 연결 실패 상황
        WHEN: 상세 정보와 함께 예외를 생성할 때
        THEN: URL, 재시도 횟수 등의 컨텍스트가 포함되어야 함
        """
        # GIVEN
        url = "wss://api.upbit.com/websocket/v1"
        retry_count = 3
        message = f"Failed to connect to {url} after {retry_count} retries"

        # WHEN
        exc = ConnectionException(message)

        # THEN
        assert url in str(exc)
        assert str(retry_count) in str(exc)

    def test_connection_exception_preserves_cause(self) -> None:
        """
        GIVEN: 네트워크 오류로 인한 연결 실패
        WHEN: 원본 네트워크 에러를 체이닝할 때
        THEN: __cause__를 통해 원본 에러를 추적할 수 있어야 함
        """
        # GIVEN
        network_error = OSError("Network unreachable")

        # WHEN
        try:
            try:
                raise network_error
            except OSError as e:
                raise ConnectionException("WebSocket connection failed") from e
        except ConnectionException as exc:
            # THEN
            assert exc.__cause__ is network_error
            assert "Network unreachable" in str(exc.__cause__)


class TestValidationException:
    """ValidationException 검증 실패 예외 테스트"""

    def test_validation_exception_inheritance(self) -> None:
        """
        GIVEN: ValidationException 클래스
        WHEN: 예외가 생성될 때
        THEN: DataIngestionException을 상속해야 함
        """
        # WHEN
        exc = ValidationException("Validation failed")

        # THEN
        assert isinstance(exc, DataIngestionException)

    def test_validation_exception_with_field_info(self) -> None:
        """
        GIVEN: 특정 필드 검증 실패
        WHEN: 필드명과 검증 규칙을 포함한 예외를 생성할 때
        THEN: 어떤 필드가 왜 실패했는지 명확해야 함
        """
        # GIVEN
        field_name = "market_code"
        value = "BTC-KRW"
        expected_format = "KRW-XXX"
        message = f"Invalid {field_name}: '{value}' (expected format: {expected_format})"

        # WHEN
        exc = ValidationException(message)

        # THEN
        assert field_name in str(exc)
        assert value in str(exc)
        assert expected_format in str(exc)

    def test_validation_exception_with_multiple_errors(self) -> None:
        """
        GIVEN: 여러 필드의 검증 실패
        WHEN: 모든 검증 에러를 포함한 예외를 생성할 때
        THEN: 모든 에러 정보가 포함되어야 함
        """
        # GIVEN
        errors = [
            "ping_interval must be >= 60 seconds",
            "subscribed_markets cannot be empty",
            "websocket_url is not a valid URL",
        ]
        message = f"Configuration validation failed: {'; '.join(errors)}"

        # WHEN
        exc = ValidationException(message)

        # THEN
        for error in errors:
            assert error in str(exc)


class TestPublishException:
    """PublishException 메시지 발행 실패 예외 테스트"""

    def test_publish_exception_inheritance(self) -> None:
        """
        GIVEN: PublishException 클래스
        WHEN: 예외가 생성될 때
        THEN: DataIngestionException을 상속해야 함
        """
        # WHEN
        exc = PublishException("Publish failed")

        # THEN
        assert isinstance(exc, DataIngestionException)

    def test_publish_exception_with_kafka_details(self) -> None:
        """
        GIVEN: Kafka 발행 실패
        WHEN: 토픽, 파티션 등의 정보와 함께 예외를 생성할 때
        THEN: Kafka 관련 상세 정보가 포함되어야 함
        """
        # GIVEN
        topic = "upbit.trades.v1"
        partition = 3
        error_code = "TIMEOUT"
        message = f"Failed to publish to {topic} (partition={partition}): {error_code}"

        # WHEN
        exc = PublishException(message)

        # THEN
        assert topic in str(exc)
        assert str(partition) in str(exc)
        assert error_code in str(exc)

    def test_publish_exception_with_broker_error(self) -> None:
        """
        GIVEN: Kafka 브로커 에러
        WHEN: 브로커 에러를 체이닝할 때
        THEN: __cause__를 통해 원본 에러를 추적할 수 있어야 함
        """
        # GIVEN
        broker_error = Exception("Broker not available")

        # WHEN
        try:
            try:
                raise broker_error
            except Exception as e:
                raise PublishException("Failed to send message to Kafka") from e
        except PublishException as exc:
            # THEN
            assert exc.__cause__ is broker_error
            assert "Broker not available" in str(exc.__cause__)


class TestExceptionJsonSerializability:
    """예외 JSON 직렬화 테스트"""

    @pytest.mark.parametrize(
        "exception_class,message",
        [
            (DataIngestionException, "Base error"),
            (ConnectionException, "Connection error"),
            (ValidationException, "Validation error"),
            (PublishException, "Publish error"),
        ],
    )
    def test_exception_is_json_serializable(
        self, exception_class: type[DataIngestionException], message: str
    ) -> None:
        """
        GIVEN: 다양한 예외 클래스들
        WHEN: 예외 정보를 JSON으로 직렬화할 때
        THEN: 예외 타입과 메시지가 직렬화 가능해야 함
        """
        # GIVEN
        exc = exception_class(message)

        # WHEN
        error_dict = {"type": exc.__class__.__name__, "message": str(exc)}
        json_str = json.dumps(error_dict)
        restored = json.loads(json_str)

        # THEN
        assert restored["type"] == exception_class.__name__
        assert restored["message"] == message

    def test_exception_with_complex_context_is_serializable(self) -> None:
        """
        GIVEN: 복잡한 컨텍스트를 포함한 예외
        WHEN: 컨텍스트를 JSON으로 직렬화할 때
        THEN: 모든 컨텍스트가 직렬화 가능해야 함
        """
        # GIVEN
        context = {
            "exchange": "upbit",
            "market": "KRW-BTC",
            "timestamp": "2024-01-01T00:00:00Z",
            "retry_count": 3,
            "error_code": "TIMEOUT",
        }
        message = "Connection failed"
        exc = ConnectionException(message)

        # WHEN
        error_dict = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "context": context,
        }
        json_str = json.dumps(error_dict)
        restored = json.loads(json_str)

        # THEN
        assert restored["context"] == context
        assert restored["type"] == "ConnectionException"



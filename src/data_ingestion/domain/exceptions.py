"""
데이터 수집 계층 예외 정의

이 모듈은 데이터 수집 계층에서 발생할 수 있는 모든 예외를 정의합니다.
모든 예외는 명확한 계층 구조를 가지며, 컨텍스트 정보를 포함하고
예외 체이닝(__cause__)을 지원합니다.

예외 계층 구조:
    Exception
    └── DataIngestionException (기본 예외)
        ├── ConnectionException (연결 관련)
        ├── ValidationException (검증 실패)
        └── PublishException (메시지 발행 실패)
"""


class DataIngestionException(Exception):
    """
    데이터 수집 계층의 기본 예외 클래스

    모든 데이터 수집 계층 예외의 부모 클래스입니다.
    이 예외를 catch하면 데이터 수집 계층의 모든 예외를 처리할 수 있습니다.

    Attributes:
        message: 예외 메시지 (컨텍스트 정보 포함)

    Examples:
        >>> try:
        ...     raise DataIngestionException("Connection failed for upbit")
        ... except DataIngestionException as e:
        ...     print(f"Error: {e}")
        Error: Connection failed for upbit

        >>> # 예외 체이닝 사용
        >>> try:
        ...     raise ValueError("Invalid data")
        ... except ValueError as e:
        ...     raise DataIngestionException("Failed to process data", cause=e)
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """
        Args:
            message: 예외 메시지. 가능한 많은 컨텍스트 정보를 포함해야 합니다.
                    (예: "Failed to connect to wss://api.upbit.com after 3 retries")
            cause: 이 예외를 발생시킨 원본 예외 (선택 사항)
        """
        self.message = message
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        """예외를 문자열로 표현"""
        if self.__cause__:
            return f"{self.message} (Caused by: {self.__cause__})"
        return self.message


class ConnectionException(DataIngestionException):
    """
    연결 관련 예외

    WebSocket 연결 실패, 재연결 실패, 타임아웃 등
    거래소와의 연결 과정에서 발생하는 모든 에러를 나타냅니다.

    Examples:
        >>> exc = ConnectionException(
        ...     "Failed to connect to wss://api.upbit.com/websocket/v1 "
        ...     "after 3 retries (timeout=30s)"
        ... )
        >>> print(exc)
        Failed to connect to wss://api.upbit.com/websocket/v1 after 3 retries (timeout=30s)

        >>> # 원본 네트워크 에러와 함께 사용
        >>> try:
        ...     raise OSError("Network unreachable")
        ... except OSError as e:
        ...     raise ConnectionException("WebSocket connection failed") from e
    """

    pass


class ConnectionFailedError(ConnectionException):
    """연결 시도 실패를 나타냅니다."""

    pass


class ConnectionClosedError(ConnectionException):
    """예상치 못하게 연결이 종료되었음을 나타냅니다."""

    pass


class RateLimitExceededError(ConnectionException):
    """API 호출 제한을 초과했음을 나타냅니다."""

    pass


class AuthenticationError(ConnectionException):
    """인증 실패를 나타냅니다."""

    pass


class ValidationException(DataIngestionException):
    """
    데이터 검증 실패 예외

    잘못된 설정값, 부적절한 마켓 코드, 필수 필드 누락 등
    비즈니스 규칙 위반이나 데이터 검증 실패를 나타냅니다.

    Examples:
        >>> exc = ValidationException(
        ...     "Invalid market_code: 'BTC-KRW' (expected format: KRW-XXX)"
        ... )
        >>> print(exc)
        Invalid market_code: 'BTC-KRW' (expected format: KRW-XXX)

        >>> # 여러 검증 에러를 한 번에
        >>> errors = [
        ...     "ping_interval must be >= 60 seconds",
        ...     "subscribed_markets cannot be empty"
        ... ]
        >>> exc = ValidationException(f"Validation failed: {'; '.join(errors)}")
    """

    pass


class InvalidMessageError(ValidationException):
    """수신된 메시지의 형식이 잘못되었거나 필수 필드가 누락되었음을 나타냅니다."""

    pass


class InvalidConfigurationError(ValidationException):
    """잘못된 설정 값을 나타냅니다."""

    pass


class InvalidTransitionError(ValidationException):
    """상태 머신에서 허용되지 않는 상태 전환을 나타냅니다."""

    pass


class PublishException(DataIngestionException):
    """
    메시지 발행 실패 예외

    Kafka 브로커 연결 실패, 메시지 전송 타임아웃, 직렬화 실패 등
    메시지를 Kafka로 발행하는 과정에서 발생하는 모든 에러를 나타냅니다.

    Examples:
        >>> exc = PublishException(
        ...     "Failed to publish to upbit.trades.v1 (partition=3): TIMEOUT"
        ... )
        >>> print(exc)
        Failed to publish to upbit.trades.v1 (partition=3): TIMEOUT

        >>> # Kafka 브로커 에러와 함께 사용
        >>> try:
        ...     raise Exception("Broker not available")
        ... except Exception as e:
        ...     raise PublishException("Failed to send message to Kafka") from e
    """

    pass


class MessageQueueFullError(PublishException):
    """메시지 큐가 가득 차서 더 이상 메시지를 추가할 수 없음을 나타냅니다."""

    pass


class MessageTooOldError(PublishException):
    """메시지가 너무 오래되어 발행할 가치가 없음을 나타냅니다."""

    pass


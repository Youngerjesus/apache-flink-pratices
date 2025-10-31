"""
업비트 거래소 전용 설정 팩토리

업비트 WebSocket 연결에 필요한 설정을 생성하는 헬퍼 함수를 제공합니다.
업비트 API 명세에 맞는 기본값(ping_interval, URL 등)을 설정합니다.
"""

from data_ingestion.domain.exceptions import InvalidConfigurationError
from data_ingestion.domain.models.exchange_config import ExchangeConfig


# 업비트 WebSocket Endpoint (시세 데이터용)
UPBIT_WEBSOCKET_URL = "wss://api.upbit.com/websocket/v1"

# 업비트 REST API Endpoint
UPBIT_REST_API_URL = "https://api.upbit.com/v1"

# 업비트 Idle Timeout (120초)를 고려한 안전한 Ping 간격 (60초)
UPBIT_PING_INTERVAL = 60

# 재연결 설정
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10
DEFAULT_EXPONENTIAL_BACKOFF_MAX = 60


def create_upbit_config(
    subscribed_markets: set[str],
    ping_interval_seconds: int = UPBIT_PING_INTERVAL,
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS,
    exponential_backoff_max_seconds: int = DEFAULT_EXPONENTIAL_BACKOFF_MAX,
) -> ExchangeConfig:
    """
    업비트 거래소 연결을 위한 ExchangeConfig를 생성합니다.

    Args:
        subscribed_markets: 구독할 마켓 코드 집합 (예: {"KRW-BTC", "KRW-ETH"})
        ping_interval_seconds: WebSocket Ping 전송 간격 (초). 기본값은 60초.
        max_reconnect_attempts: 최대 재연결 시도 횟수. 0이면 무한 재시도.
        exponential_backoff_max_seconds: 지수 백오프 최대 대기 시간 (초)

    Returns:
        업비트 연결 설정이 담긴 ExchangeConfig 객체

    Raises:
        InvalidConfigurationError: 설정 검증 실패 시

    Examples:
        >>> config = create_upbit_config({"KRW-BTC", "KRW-ETH"})
        >>> print(config.exchange_name)
        'upbit'
        >>> print(config.ping_interval_seconds)
        60
    """
    # 업비트 전용 검증: Idle Timeout(120초) 대응
    if ping_interval_seconds < 60:
        raise InvalidConfigurationError(
            "Upbit ping_interval must be >= 60 seconds to prevent 120s idle timeout"
        )

    # 마켓 코드 대문자 정규화 (업비트 API 요구사항)
    normalized_markets = {code.upper() for code in subscribed_markets}

    return ExchangeConfig(
        exchange_name="upbit",
        websocket_url=UPBIT_WEBSOCKET_URL,
        rest_api_url=UPBIT_REST_API_URL,
        subscribed_markets=normalized_markets,
        ping_interval_seconds=ping_interval_seconds,
        max_reconnect_attempts=max_reconnect_attempts,
        exponential_backoff_max_seconds=exponential_backoff_max_seconds,
    )


"""
업비트 설정 팩토리 테스트
"""

import pytest

from data_ingestion.infrastructure.connectors.upbit_config import (
    UPBIT_PING_INTERVAL,
    UPBIT_REST_API_URL,
    UPBIT_WEBSOCKET_URL,
    create_upbit_config,
)


class TestCreateUpbitConfig:
    """create_upbit_config 함수 테스트"""

    def test_basic_config_creation(self) -> None:
        """
        GIVEN: 기본 마켓 코드 집합
        WHEN: create_upbit_config를 호출할 때
        THEN: 올바른 업비트 설정이 생성되어야 함
        """
        # GIVEN
        markets = {"KRW-BTC", "KRW-ETH"}

        # WHEN
        config = create_upbit_config(subscribed_markets=markets)

        # THEN
        assert config.exchange_name == "upbit"
        assert config.websocket_url == UPBIT_WEBSOCKET_URL
        assert config.rest_api_url == UPBIT_REST_API_URL
        assert config.subscribed_markets == frozenset(markets)
        assert config.ping_interval_seconds == UPBIT_PING_INTERVAL

    def test_custom_ping_interval(self) -> None:
        """
        GIVEN: 커스텀 ping interval 값
        WHEN: create_upbit_config에 전달할 때
        THEN: 해당 값이 설정에 반영되어야 함
        """
        # GIVEN
        markets = {"KRW-BTC"}
        custom_ping = 90

        # WHEN
        config = create_upbit_config(
            subscribed_markets=markets, ping_interval_seconds=custom_ping
        )

        # THEN
        assert config.ping_interval_seconds == custom_ping

    def test_custom_reconnect_settings(self) -> None:
        """
        GIVEN: 커스텀 재연결 설정
        WHEN: create_upbit_config에 전달할 때
        THEN: 해당 설정이 올바르게 반영되어야 함
        """
        # GIVEN
        markets = {"KRW-BTC"}
        max_attempts = 5
        max_backoff = 120

        # WHEN
        config = create_upbit_config(
            subscribed_markets=markets,
            max_reconnect_attempts=max_attempts,
            exponential_backoff_max_seconds=max_backoff,
        )

        # THEN
        assert config.max_reconnect_attempts == max_attempts
        assert config.exponential_backoff_max_seconds == max_backoff

    def test_market_code_normalization(self) -> None:
        """
        GIVEN: 소문자 마켓 코드
        WHEN: create_upbit_config를 호출할 때
        THEN: 대문자로 정규화되어야 함
        """
        # GIVEN
        markets = {"krw-btc", "KRW-eth", "KRW-XRP"}

        # WHEN
        config = create_upbit_config(subscribed_markets=markets)

        # THEN
        assert config.subscribed_markets == frozenset(
            {"KRW-BTC", "KRW-ETH", "KRW-XRP"}
        )

    def test_empty_markets_raises_error(self) -> None:
        """
        GIVEN: 빈 마켓 코드 집합
        WHEN: create_upbit_config를 호출할 때
        THEN: InvalidConfigurationError가 발생해야 함
        """
        # GIVEN
        markets = set()

        # WHEN / THEN
        from data_ingestion.domain.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError, match="subscribed_markets"):
            create_upbit_config(subscribed_markets=markets)

    def test_invalid_ping_interval_raises_error(self) -> None:
        """
        GIVEN: 60초 미만의 ping interval
        WHEN: create_upbit_config를 호출할 때
        THEN: InvalidConfigurationError가 발생해야 함 (업비트 Idle Timeout 대응)
        """
        # GIVEN
        markets = {"KRW-BTC"}
        invalid_ping = 30

        # WHEN / THEN
        from data_ingestion.domain.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError, match="ping_interval"):
            create_upbit_config(
                subscribed_markets=markets, ping_interval_seconds=invalid_ping
            )

    def test_config_immutability(self) -> None:
        """
        GIVEN: 생성된 ExchangeConfig
        WHEN: subscribed_markets를 수정하려고 시도할 때
        THEN: 수정이 불가능해야 함 (frozen dataclass)
        """
        # GIVEN
        config = create_upbit_config(subscribed_markets={"KRW-BTC"})

        # WHEN / THEN
        with pytest.raises(AttributeError):
            config.subscribed_markets = {"KRW-ETH"}  # type: ignore

    def test_multiple_markets(self) -> None:
        """
        GIVEN: 여러 마켓 코드
        WHEN: create_upbit_config를 호출할 때
        THEN: 모든 마켓이 올바르게 설정되어야 함
        """
        # GIVEN
        markets = {"KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL"}

        # WHEN
        config = create_upbit_config(subscribed_markets=markets)

        # THEN
        assert len(config.subscribed_markets) == 5
        assert config.subscribed_markets == frozenset(markets)

    def test_config_validation_passes(self) -> None:
        """
        GIVEN: 유효한 마켓 코드와 설정
        WHEN: create_upbit_config를 호출할 때
        THEN: 검증을 통과하고 정상적으로 설정이 생성되어야 함
        """
        # GIVEN
        markets = {"KRW-BTC", "KRW-ETH"}

        # WHEN
        config = create_upbit_config(subscribed_markets=markets)

        # THEN
        config.validate()  # 예외가 발생하지 않아야 함


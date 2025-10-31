"""
ConnectionState 연결 상태 Enum 테스트

이 테스트 모듈은 거래소 커넥터의 연결 상태를 나타내는 Enum을 검증합니다.
상태 전환 규칙을 엄격하게 검증하여 잘못된 상태 변경을 방지합니다.
"""

import pytest

from data_ingestion.domain.models.connection_state import (
    ConnectionState,
    InvalidTransitionError,
)


class TestConnectionStateEnum:
    """ConnectionState Enum 기본 기능 테스트"""

    def test_enum_values_exist(self) -> None:
        """
        GIVEN: ConnectionState Enum
        WHEN: 모든 필수 상태값을 확인할 때
        THEN: DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, FAILED 상태가 존재해야 함
        """
        # THEN
        assert ConnectionState.DISCONNECTED
        assert ConnectionState.CONNECTING
        assert ConnectionState.CONNECTED
        assert ConnectionState.RECONNECTING
        assert ConnectionState.FAILED

    def test_enum_immutability(self) -> None:
        """
        GIVEN: ConnectionState Enum 값
        WHEN: 값을 변경하려고 시도할 때
        THEN: 불변성이 보장되어야 함 (Enum은 기본적으로 불변)
        """
        # GIVEN
        state = ConnectionState.CONNECTED

        # THEN - Enum은 불변이므로 재할당만 가능하고 값 자체는 변경 불가
        assert isinstance(state, ConnectionState)
        assert state == ConnectionState.CONNECTED

    def test_enum_can_be_compared(self) -> None:
        """
        GIVEN: 두 개의 ConnectionState 값
        WHEN: 값을 비교할 때
        THEN: 동일성 비교가 가능해야 함
        """
        # GIVEN
        state1 = ConnectionState.CONNECTED
        state2 = ConnectionState.CONNECTED
        state3 = ConnectionState.CONNECTING

        # THEN
        assert state1 == state2
        assert state1 is state2  # Enum은 싱글톤
        assert state1 != state3

    def test_enum_has_string_representation(self) -> None:
        """
        GIVEN: ConnectionState 값
        WHEN: 문자열로 변환할 때
        THEN: 명확한 문자열 표현을 가져야 함
        """
        # GIVEN
        state = ConnectionState.CONNECTED

        # THEN
        assert "CONNECTED" in str(state)
        assert state.name == "CONNECTED"


class TestConnectionStateTransitions:
    """ConnectionState 상태 전환 규칙 테스트"""

    def test_initial_state_to_connecting(self) -> None:
        """
        GIVEN: DISCONNECTED 상태
        WHEN: CONNECTING으로 전환을 시도할 때
        THEN: 전환이 허용되어야 함
        """
        # GIVEN
        current = ConnectionState.DISCONNECTED
        target = ConnectionState.CONNECTING

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_connecting_to_connected(self) -> None:
        """
        GIVEN: CONNECTING 상태
        WHEN: CONNECTED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함
        """
        # GIVEN
        current = ConnectionState.CONNECTING
        target = ConnectionState.CONNECTED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_connecting_to_failed(self) -> None:
        """
        GIVEN: CONNECTING 상태
        WHEN: FAILED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (연결 시도 중 실패 가능)
        """
        # GIVEN
        current = ConnectionState.CONNECTING
        target = ConnectionState.FAILED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_connected_to_disconnected(self) -> None:
        """
        GIVEN: CONNECTED 상태
        WHEN: DISCONNECTED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (정상적인 연결 해제)
        """
        # GIVEN
        current = ConnectionState.CONNECTED
        target = ConnectionState.DISCONNECTED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_connected_to_failed(self) -> None:
        """
        GIVEN: CONNECTED 상태
        WHEN: FAILED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (연결 중 오류 발생 가능)
        """
        # GIVEN
        current = ConnectionState.CONNECTED
        target = ConnectionState.FAILED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_failed_to_disconnected(self) -> None:
        """
        GIVEN: FAILED 상태
        WHEN: DISCONNECTED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (실패 후 정리)
        """
        # GIVEN
        current = ConnectionState.FAILED
        target = ConnectionState.DISCONNECTED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_connected_to_reconnecting(self) -> None:
        """
        GIVEN: CONNECTED 상태
        WHEN: RECONNECTING으로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (예상치 못한 연결 끊김)
        """
        # GIVEN
        current = ConnectionState.CONNECTED
        target = ConnectionState.RECONNECTING

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_reconnecting_to_connected(self) -> None:
        """
        GIVEN: RECONNECTING 상태
        WHEN: CONNECTED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (재연결 성공)
        """
        # GIVEN
        current = ConnectionState.RECONNECTING
        target = ConnectionState.CONNECTED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_reconnecting_to_failed(self) -> None:
        """
        GIVEN: RECONNECTING 상태
        WHEN: FAILED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (재시도 횟수 초과)
        """
        # GIVEN
        current = ConnectionState.RECONNECTING
        target = ConnectionState.FAILED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_reconnecting_to_disconnected(self) -> None:
        """
        GIVEN: RECONNECTING 상태
        WHEN: DISCONNECTED로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (수동 종료)
        """
        # GIVEN
        current = ConnectionState.RECONNECTING
        target = ConnectionState.DISCONNECTED

        # WHEN / THEN
        assert current.is_valid_transition(target)

    def test_failed_to_connecting_not_allowed(self) -> None:
        """
        GIVEN: FAILED 상태
        WHEN: CONNECTING으로 직접 전환을 시도할 때
        THEN: 전환이 거부되어야 함 (먼저 DISCONNECTED로 돌아가야 함)
        """
        # GIVEN
        current = ConnectionState.FAILED
        target = ConnectionState.CONNECTING

        # WHEN / THEN
        assert not current.is_valid_transition(target)

    def test_connected_to_connecting_not_allowed(self) -> None:
        """
        GIVEN: CONNECTED 상태
        WHEN: CONNECTING으로 전환을 시도할 때
        THEN: 전환이 거부되어야 함 (이미 연결됨)
        """
        # GIVEN
        current = ConnectionState.CONNECTED
        target = ConnectionState.CONNECTING

        # WHEN / THEN
        assert not current.is_valid_transition(target)

    def test_disconnected_to_reconnecting_not_allowed(self) -> None:
        """
        GIVEN: DISCONNECTED 상태
        WHEN: RECONNECTING으로 전환을 시도할 때
        THEN: 전환이 거부되어야 함 (첫 연결은 CONNECTING으로)
        """
        # GIVEN
        current = ConnectionState.DISCONNECTED
        target = ConnectionState.RECONNECTING

        # WHEN / THEN
        assert not current.is_valid_transition(target)

    def test_connecting_to_reconnecting_not_allowed(self) -> None:
        """
        GIVEN: CONNECTING 상태
        WHEN: RECONNECTING으로 전환을 시도할 때
        THEN: 전환이 거부되어야 함 (연결 시도 중에는 재연결 불가)
        """
        # GIVEN
        current = ConnectionState.CONNECTING
        target = ConnectionState.RECONNECTING

        # WHEN / THEN
        assert not current.is_valid_transition(target)

    def test_reconnecting_to_connecting_not_allowed(self) -> None:
        """
        GIVEN: RECONNECTING 상태
        WHEN: CONNECTING으로 전환을 시도할 때
        THEN: 전환이 거부되어야 함 (무한 루프 방지)
        """
        # GIVEN
        current = ConnectionState.RECONNECTING
        target = ConnectionState.CONNECTING

        # WHEN / THEN
        assert not current.is_valid_transition(target)

    def test_same_state_transition_allowed(self) -> None:
        """
        GIVEN: 임의의 상태
        WHEN: 동일한 상태로 전환을 시도할 때
        THEN: 전환이 허용되어야 함 (멱등성)
        """
        # GIVEN / WHEN / THEN
        for state in ConnectionState:
            assert state.is_valid_transition(state)

    @pytest.mark.parametrize(
        "current,target,expected",
        [
            # 허용되는 전환
            (ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, True),
            (ConnectionState.CONNECTING, ConnectionState.CONNECTED, True),
            (ConnectionState.CONNECTING, ConnectionState.FAILED, True),
            (ConnectionState.CONNECTED, ConnectionState.DISCONNECTED, True),
            (ConnectionState.CONNECTED, ConnectionState.RECONNECTING, True),
            (ConnectionState.CONNECTED, ConnectionState.FAILED, True),
            (ConnectionState.RECONNECTING, ConnectionState.CONNECTED, True),
            (ConnectionState.RECONNECTING, ConnectionState.FAILED, True),
            (ConnectionState.RECONNECTING, ConnectionState.DISCONNECTED, True),
            (ConnectionState.FAILED, ConnectionState.DISCONNECTED, True),
            # 거부되는 전환
            (ConnectionState.DISCONNECTED, ConnectionState.CONNECTED, False),
            (ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING, False),
            (ConnectionState.DISCONNECTED, ConnectionState.FAILED, False),
            (ConnectionState.CONNECTING, ConnectionState.DISCONNECTED, False),
            (ConnectionState.CONNECTING, ConnectionState.RECONNECTING, False),
            (ConnectionState.CONNECTED, ConnectionState.CONNECTING, False),
            (ConnectionState.RECONNECTING, ConnectionState.CONNECTING, False),
            (ConnectionState.FAILED, ConnectionState.CONNECTING, False),
            (ConnectionState.FAILED, ConnectionState.CONNECTED, False),
            (ConnectionState.FAILED, ConnectionState.RECONNECTING, False),
        ],
    )
    def test_transition_matrix(
        self, current: ConnectionState, target: ConnectionState, expected: bool
    ) -> None:
        """
        GIVEN: 다양한 현재 상태와 목표 상태 조합
        WHEN: 상태 전환 가능 여부를 확인할 때
        THEN: 전환 매트릭스에 정의된 대로 결과가 나와야 함
        """
        # WHEN
        result = current.is_valid_transition(target)

        # THEN
        assert result == expected, f"{current.name} -> {target.name} should be {expected}"


class TestConnectionStateValidation:
    """ConnectionState 전환 검증 메서드 테스트"""

    def test_validate_transition_success(self) -> None:
        """
        GIVEN: 허용되는 상태 전환
        WHEN: validate_transition()을 호출할 때
        THEN: 예외가 발생하지 않아야 함
        """
        # GIVEN
        current = ConnectionState.CONNECTING
        target = ConnectionState.CONNECTED

        # WHEN / THEN - 예외가 발생하지 않아야 함
        current.validate_transition(target)

    def test_validate_transition_failure_raises_exception(self) -> None:
        """
        GIVEN: 허용되지 않는 상태 전환
        WHEN: validate_transition()을 호출할 때
        THEN: InvalidTransitionError 예외가 발생해야 함
        """
        # GIVEN
        current = ConnectionState.FAILED
        target = ConnectionState.CONNECTING

        # WHEN / THEN
        with pytest.raises(InvalidTransitionError) as exc_info:
            current.validate_transition(target)

        # 예외 메시지에 현재 상태와 목표 상태가 포함되어야 함
        assert "FAILED" in str(exc_info.value)
        assert "CONNECTING" in str(exc_info.value)

    def test_validate_transition_error_is_validation_exception(self) -> None:
        """
        GIVEN: InvalidTransitionError
        WHEN: 예외 타입을 확인할 때
        THEN: ValidationException을 상속해야 함
        """
        # GIVEN
        from data_ingestion.domain.exceptions import ValidationException

        current = ConnectionState.CONNECTED
        target = ConnectionState.CONNECTING

        # WHEN
        try:
            current.validate_transition(target)
            pytest.fail("Should have raised InvalidTransitionError")
        except InvalidTransitionError as e:
            # THEN
            assert isinstance(e, ValidationException)


class TestConnectionStateHistory:
    """ConnectionState 전환 히스토리 추적 테스트"""

    def test_transition_history_records_changes(self) -> None:
        """
        GIVEN: StateTransitionTracker 인스턴스
        WHEN: 여러 상태 전환을 기록할 때
        THEN: 모든 전환이 순서대로 기록되어야 함
        """
        # GIVEN
        from data_ingestion.domain.models.connection_state import StateTransitionTracker

        tracker = StateTransitionTracker()

        # WHEN
        tracker.record_transition(
            ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, "Starting connection"
        )
        tracker.record_transition(
            ConnectionState.CONNECTING, ConnectionState.CONNECTED, "Connection established"
        )

        # THEN
        history = tracker.get_history()
        assert len(history) == 2
        assert history[0]["from_state"] == ConnectionState.DISCONNECTED
        assert history[0]["to_state"] == ConnectionState.CONNECTING
        assert history[1]["from_state"] == ConnectionState.CONNECTING
        assert history[1]["to_state"] == ConnectionState.CONNECTED

    def test_transition_history_records_reconnection_flow(self) -> None:
        """
        GIVEN: StateTransitionTracker 인스턴스
        WHEN: 재연결 흐름을 기록할 때
        THEN: CONNECTED -> RECONNECTING -> CONNECTED 전환이 기록되어야 함
        """
        # GIVEN
        from data_ingestion.domain.models.connection_state import StateTransitionTracker

        tracker = StateTransitionTracker()

        # WHEN
        tracker.record_transition(
            ConnectionState.CONNECTED, ConnectionState.RECONNECTING, "Connection lost"
        )
        tracker.record_transition(
            ConnectionState.RECONNECTING, ConnectionState.CONNECTED, "Reconnection successful"
        )

        # THEN
        history = tracker.get_history()
        assert len(history) == 2
        assert history[0]["from_state"] == ConnectionState.CONNECTED
        assert history[0]["to_state"] == ConnectionState.RECONNECTING
        assert history[0]["reason"] == "Connection lost"
        assert history[1]["from_state"] == ConnectionState.RECONNECTING
        assert history[1]["to_state"] == ConnectionState.CONNECTED
        assert history[1]["reason"] == "Reconnection successful"

    def test_transition_history_includes_timestamp(self) -> None:
        """
        GIVEN: StateTransitionTracker 인스턴스
        WHEN: 상태 전환을 기록할 때
        THEN: 각 전환에 타임스탬프가 포함되어야 함
        """
        # GIVEN
        from data_ingestion.domain.models.connection_state import StateTransitionTracker

        tracker = StateTransitionTracker()

        # WHEN
        tracker.record_transition(
            ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, "Starting"
        )

        # THEN
        history = tracker.get_history()
        assert "timestamp" in history[0]
        assert history[0]["timestamp"] is not None

    def test_transition_history_can_be_cleared(self) -> None:
        """
        GIVEN: 히스토리가 있는 StateTransitionTracker
        WHEN: 히스토리를 클리어할 때
        THEN: 모든 기록이 제거되어야 함
        """
        # GIVEN
        from data_ingestion.domain.models.connection_state import StateTransitionTracker

        tracker = StateTransitionTracker()
        tracker.record_transition(
            ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, "Starting"
        )

        # WHEN
        tracker.clear_history()

        # THEN
        assert len(tracker.get_history()) == 0


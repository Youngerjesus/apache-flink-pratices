"""
거래소 연결 상태 모델

거래소 커넥터의 연결 상태를 나타내는 Enum과 상태 전환 검증 로직을 제공합니다.
상태 전환은 엄격하게 검증되어 잘못된 상태 변경을 방지합니다.

상태 전환 다이어그램:
    DISCONNECTED --> CONNECTING --> CONNECTED
         ^                |             |
         |                v             v
         +------------- FAILED          |
                                        v
                                   RECONNECTING
                                   |    |    |
                                   v    v    v
                             CONNECTED FAILED DISCONNECTED
"""

from datetime import UTC, datetime
from enum import Enum

from data_ingestion.domain.exceptions import InvalidTransitionError


class ConnectionState(Enum):
    """
    거래소 커넥터 연결 상태

    WebSocket 연결의 생명주기를 나타내는 상태입니다.
    각 상태 간 전환은 명확한 규칙을 따라야 합니다.

    Attributes:
        DISCONNECTED: 연결되지 않은 상태 (초기 상태)
        CONNECTING: 연결 시도 중
        CONNECTED: 연결 완료
        RECONNECTING: 예상치 못한 연결 끊김 후 재연결 시도 중
        FAILED: 연결 실패 (재시도 전 정리 필요)

    Examples:
        >>> state = ConnectionState.DISCONNECTED
        >>> state.is_valid_transition(ConnectionState.CONNECTING)
        True
        >>> state.is_valid_transition(ConnectionState.CONNECTED)
        False
    """

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

    @classmethod
    def _get_valid_transitions(cls) -> dict["ConnectionState", set["ConnectionState"]]:
        """
        상태 전환 허용 매트릭스 반환
        
        Returns:
            Key: 현재 상태, Value: 전환 가능한 상태들
        
        상태 전환 규칙:
            - DISCONNECTED: 첫 연결은 CONNECTING으로만 가능
            - CONNECTING: 성공 시 CONNECTED, 실패 시 FAILED
            - CONNECTED: 정상 종료(DISCONNECTED), 재연결 가능한 끊김(RECONNECTING), 
                        치명적 오류(FAILED)
            - RECONNECTING: 재연결 성공(CONNECTED), 실패(FAILED), 수동 종료(DISCONNECTED)
            - FAILED: 정리 후 DISCONNECTED로만 전환 가능
        """
        return {
            cls.DISCONNECTED: {cls.CONNECTING},
            cls.CONNECTING: {cls.CONNECTED, cls.FAILED},
            cls.CONNECTED: {cls.DISCONNECTED, cls.RECONNECTING, cls.FAILED},
            cls.RECONNECTING: {cls.CONNECTED, cls.FAILED, cls.DISCONNECTED},
            cls.FAILED: {cls.DISCONNECTED},
        }

    def is_valid_transition(self, target: "ConnectionState") -> bool:
        """
        특정 상태로의 전환이 가능한지 확인

        Args:
            target: 전환하려는 목표 상태

        Returns:
            전환 가능 여부 (True/False)

        Examples:
            >>> ConnectionState.DISCONNECTED.is_valid_transition(ConnectionState.CONNECTING)
            True
            >>> ConnectionState.FAILED.is_valid_transition(ConnectionState.CONNECTING)
            False
        """
        # 동일한 상태로의 전환은 항상 허용 (멱등성)
        if self == target:
            return True

        # 전환 매트릭스에서 확인
        transitions = self._get_valid_transitions()
        return target in transitions.get(self, set())

    def validate_transition(self, target: "ConnectionState") -> None:
        """
        상태 전환 유효성 검증

        Args:
            target: 전환하려는 목표 상태

        Raises:
            InvalidTransitionError: 허용되지 않는 전환인 경우

        Examples:
            >>> state = ConnectionState.CONNECTING
            >>> state.validate_transition(ConnectionState.CONNECTED)  # OK
            >>> state.validate_transition(ConnectionState.DISCONNECTED)  # Raises exception
            Traceback (most recent call last):
                ...
            InvalidTransitionError: Invalid state transition: CONNECTING -> DISCONNECTED
        """
        if not self.is_valid_transition(target):
            transitions = self._get_valid_transitions()
            valid_transitions = transitions.get(self, set())
            raise InvalidTransitionError(
                f"Invalid state transition: {self.name} -> {target.name}. "
                f"Valid transitions from {self.name} are: "
                f"{', '.join(s.name for s in valid_transitions)}"
            )


class StateTransitionTracker:
    """
    상태 전환 히스토리 추적기

    디버깅 및 모니터링을 위해 상태 전환 이력을 기록합니다.

    Attributes:
        _history: 상태 전환 기록 리스트

    Examples:
        >>> tracker = StateTransitionTracker()
        >>> tracker.record_transition(
        ...     ConnectionState.DISCONNECTED,
        ...     ConnectionState.CONNECTING,
        ...     "Starting connection"
        ... )
        >>> history = tracker.get_history()
        >>> len(history)
        1
    """

    def __init__(self) -> None:
        """StateTransitionTracker 초기화"""
        self._history: list[dict[str, object]] = []

    def record_transition(
        self, from_state: ConnectionState, to_state: ConnectionState, reason: str
    ) -> None:
        """
        상태 전환 기록

        Args:
            from_state: 이전 상태
            to_state: 새로운 상태
            reason: 전환 사유

        Examples:
            >>> tracker = StateTransitionTracker()
            >>> tracker.record_transition(
            ...     ConnectionState.CONNECTING,
            ...     ConnectionState.CONNECTED,
            ...     "WebSocket handshake completed"
            ... )
        """
        self._history.append(
            {
                "timestamp": datetime.now(UTC),
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
            }
        )

    def get_history(self) -> list[dict[str, object]]:
        """
        전환 히스토리 조회

        Returns:
            상태 전환 기록 리스트

        Examples:
            >>> tracker = StateTransitionTracker()
            >>> tracker.record_transition(
            ...     ConnectionState.DISCONNECTED,
            ...     ConnectionState.CONNECTING,
            ...     "Initial connection"
            ... )
            >>> history = tracker.get_history()
            >>> history[0]["reason"]
            'Initial connection'
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """
        히스토리 초기화

        Examples:
            >>> tracker = StateTransitionTracker()
            >>> tracker.record_transition(
            ...     ConnectionState.DISCONNECTED,
            ...     ConnectionState.CONNECTING,
            ...     "Test"
            ... )
            >>> tracker.clear_history()
            >>> len(tracker.get_history())
            0
        """
        self._history.clear()


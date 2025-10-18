"""
Data Source 예제

Flink의 다양한 소스(Source)를 사용하는 예제입니다.
"""

from pyflink.datastream import StreamExecutionEnvironment


def collection_source_example() -> None:
    """컬렉션 소스 예제"""
    env = StreamExecutionEnvironment.get_execution_environment()

    # Python 리스트로부터 데이터 스트림 생성
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ds = env.from_collection(collection=data)

    # 짝수만 필터링
    even_numbers = ds.filter(lambda x: x % 2 == 0)

    # 결과 출력
    even_numbers.print()

    env.execute("Collection Source Example")


def element_source_example() -> None:
    """개별 요소 소스 예제"""
    env = StreamExecutionEnvironment.get_execution_environment()

    # 개별 요소로부터 데이터 스트림 생성
    ds = env.from_collection(collection=[
        {"user_id": 1, "event": "login", "timestamp": "2025-01-01 10:00:00"},
        {"user_id": 2, "event": "purchase", "timestamp": "2025-01-01 10:05:00"},
        {"user_id": 1, "event": "logout", "timestamp": "2025-01-01 10:30:00"},
    ])

    # 이벤트 타입별 필터링
    login_events = ds.filter(lambda x: x["event"] == "login")

    # 결과 출력
    login_events.print()

    env.execute("Element Source Example")


if __name__ == "__main__":
    print("=" * 50)
    print("Collection Source Example")
    print("=" * 50)
    collection_source_example()

    print("\n" + "=" * 50)
    print("Element Source Example")
    print("=" * 50)
    element_source_example()


"""
간단한 Word Count 예제

이 예제는 PyFlink의 DataStream API를 사용하여
텍스트 스트림에서 단어를 세는 기본적인 작업을 보여줍니다.
"""

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import MapFunction, ReduceFunction
from pyflink.common.typeinfo import Types


class Tokenizer(MapFunction):
    """텍스트를 단어로 분리하는 함수"""

    def map(self, value: str) -> tuple:
        for word in value.lower().split():
            yield (word, 1)


class Sum(ReduceFunction):
    """단어별 카운트를 합산하는 함수"""

    def reduce(self, value1: tuple, value2: tuple) -> tuple:
        return (value1[0], value1[1] + value2[1])


def word_count_example() -> None:
    """Word Count 예제 실행 함수"""
    # 실행 환경 생성
    env = StreamExecutionEnvironment.get_execution_environment()

    # 샘플 데이터 스트림 생성
    text_data = [
        "Apache Flink는 강력한 스트림 처리 프레임워크입니다",
        "Flink를 사용하면 실시간 데이터 처리가 가능합니다",
        "스트림 처리는 현대 데이터 엔지니어링의 핵심입니다",
    ]

    # 데이터 소스 생성
    ds = env.from_collection(collection=text_data)

    # 데이터 변환: 단어 분리 및 카운트
    word_count = (
        ds.flat_map(Tokenizer(), output_type=Types.TUPLE([Types.STRING(), Types.INT()]))
        .key_by(lambda x: x[0])
        .reduce(Sum())
    )

    # 결과 출력
    word_count.print()

    # 실행
    env.execute("Word Count Example")


if __name__ == "__main__":
    word_count_example()


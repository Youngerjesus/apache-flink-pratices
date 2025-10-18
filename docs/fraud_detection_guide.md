# Fraud Detection Job 실행 가이드

## 개요

이 문서는 Java로 작성된 FraudDetectionJob을 Python(PyFlink)으로 변환한 예제의 실행 가이드입니다.

## 구현 내용

### 사기 감지 로직

**패턴**: 소액 거래 후 1분 내 고액 거래

1. **소액 거래** (≤ $1.00) 감지 시:
   - 계정 상태에 플래그 저장
   - 1분 타이머 등록

2. **고액 거래** (≥ $500.00) 감지 시:
   - 이전에 소액 거래가 있었다면 → 🚨 Alert 생성
   - 그렇지 않으면 → 정상 거래

3. **타이머 만료** (1분 경과):
   - 상태 초기화
   - 다음 거래부터 새로운 패턴 감지 시작

### 아키텍처

```
Transaction Source
       ↓
  Key by Account ID
       ↓
  FraudDetector (KeyedProcessFunction)
   - ValueState: 소액 거래 플래그
   - Timer: 1분 타이머
       ↓
    Alert Sink
```

## 실행 방법

### 1. 환경 준비

```bash
# 의존성 설치
poetry install

# 가상환경 활성화
poetry shell
```

### 2. Flink 클러스터 시작 (선택사항)

Docker를 사용하여 Flink 클러스터를 시작할 수 있습니다:

```bash
# 클러스터 시작
make docker-up

# 준비 대기
make docker-wait

# Web UI 확인: http://localhost:8081
```

> **참고**: 로컬 모드에서도 실행 가능하므로 클러스터 시작은 선택사항입니다.

### 3. Job 실행

#### 방법 1: Make 명령 사용 (권장)

```bash
make fraud-run
```

#### 방법 2: Python 직접 실행

```bash
poetry run python examples/fraud_detection_job.py
```

### 4. 결과 확인

실행하면 다음과 같은 결과를 확인할 수 있습니다:

```
================================================================================
Fraud Detection Job 시작
================================================================================

샘플 트랜잭션을 처리하고 있습니다...
예상 결과: 계정 3과 4에서 사기 거래 감지

🚨 FRAUD ALERT: 소액 거래 후 1분 내 고액 거래 감지: $600.00 (계정: 3)
🚨 FRAUD ALERT: 소액 거래 후 1분 내 고액 거래 감지: $500.00 (계정: 4)
🚨 FRAUD ALERT: 소액 거래 후 1분 내 고액 거래 감지: $999.00 (계정: 3)

================================================================================
Fraud Detection Job 완료
================================================================================
```

## 샘플 데이터 설명

구현에는 다양한 패턴의 샘플 데이터가 포함되어 있습니다:

### 정상 패턴 (Alert 없음)

- **계정 1**: 고액 거래만
  - $600 → $700 (정상)
  
- **계정 2**: 소액 거래 후 1분 이상 경과 후 고액 거래
  - $0.50 → (70초 후) $600 (정상, 1분 초과)
  
- **계정 5**: 소액 거래만
  - $0.10 → $0.50 (정상)

### 사기 패턴 (Alert 발생) 🚨

- **계정 3**: 소액 → 30초 후 고액
  - $0.50 → (30초 후) $600.00 ⚠️ 사기 감지!
  - $0.99 → (30초 후) $999.00 ⚠️ 사기 감지!
  
- **계정 4**: 소액 → 30초 후 고액
  - $1.00 → (30초 후) $500.00 ⚠️ 사기 감지!

## 테스트

### 단위 테스트 실행

```bash
# 전체 테스트
make test

# 커버리지 포함
make test-cov

# Fraud Detection 테스트만
poetry run pytest tests/test_fraud_detection.py -v
```

### 테스트 항목

- ✅ Transaction/Alert 엔티티 생성 및 문자열 변환
- ✅ 샘플 데이터 생성 및 패턴 검증
- ✅ FraudDetector 상수값 검증
- ✅ 소액/고액 거래 분류 로직
- ✅ Job 생성 가능 여부
- ✅ 샘플 데이터 계정 포함 여부

## 코드 구조

```
src/pyflink_examples/fraud_detection/
├── __init__.py           # 패키지 초기화
├── entities.py           # Transaction, Alert 데이터 클래스
├── fraud_detector.py     # FraudDetector (KeyedProcessFunction)
└── job.py               # Job 구성 및 실행

examples/
└── fraud_detection_job.py  # 실행 스크립트

tests/
└── test_fraud_detection.py # 단위 테스트
```

## 주요 구현 포인트

### 1. KeyedProcessFunction 사용

```python
class FraudDetector(KeyedProcessFunction):
    def process_element(self, transaction, ctx):
        # 계정별로 상태를 관리하며 처리
        ...
    
    def on_timer(self, timestamp, ctx):
        # 타이머 만료 시 상태 정리
        ...
```

### 2. 상태 관리

```python
def open(self, runtime_context):
    # Boolean 플래그 상태
    self.flag_state = runtime_context.get_state(Types.BOOLEAN())
    
    # Long 타이머 상태
    self.timer_state = runtime_context.get_state(Types.LONG())
```

### 3. 타이머 등록

```python
# 1분 후 타이머 등록
timer_time = transaction.timestamp + self.ONE_MINUTE
ctx.timer_service().register_event_time_timer(timer_time)
```

## 코드 품질

### 포맷팅

```bash
make format
```

### 린트

```bash
make lint
```

### 타입 체크

```bash
make typecheck
```

## Java 코드와의 비교

| 항목 | Java | Python (PyFlink) |
|------|------|------------------|
| 엔티티 | POJO 클래스 | `@dataclass` |
| 상태 관리 | `ValueState<Boolean>` | `runtime_context.get_state(Types.BOOLEAN())` |
| 타이머 | `registerEventTimeTimer()` | `register_event_time_timer()` |
| 키 분할 | `keyBy(Transaction::getAccountId)` | `key_by(lambda t: t.account_id)` |
| 타입 정보 | 자동 추론 | 명시적 지정 (`Types.PICKLED_BYTE_ARRAY()`) |

## 트러블슈팅

### 1. 임포트 에러

```
ModuleNotFoundError: No module named 'pyflink'
```

**해결**: Poetry 환경 활성화
```bash
poetry install
poetry shell
```

### 2. Java 버전 에러 (Docker 미사용 시)

```
Error: Java version mismatch
```

**해결**: Java 11 이상 설치 확인
```bash
java -version
```

### 3. 결과가 출력되지 않음

**원인**: 병렬도 설정 또는 데이터 순서 문제

**해결**: `job.py`에서 병렬도 확인
```python
env.set_parallelism(1)
```

## 다음 단계

1. **실시간 소스 연동**: Kafka, Socket 등 실시간 데이터 소스 연결
2. **복잡한 패턴**: CEP(Complex Event Processing) 라이브러리 활용
3. **Alert 싱크**: 외부 시스템(DB, 알림 시스템)으로 Alert 전송
4. **성능 최적화**: 상태 TTL, 병렬도 조정
5. **모니터링**: Flink 메트릭 및 로깅 설정

## 참고 자료

- [Apache Flink 공식 문서](https://flink.apache.org/docs/stable/)
- [PyFlink 문서](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/dev/python/overview/)
- [Flink Fraud Detection 튜토리얼](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/try-flink/datastream/)


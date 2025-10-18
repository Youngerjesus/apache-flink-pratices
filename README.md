# Apache Flink 실습 프로젝트

Apache Flink를 사용한 스트림 처리 실습을 위한 프로젝트입니다.

> 🚀 **빠르게 시작하기**: [QUICKSTART.md](QUICKSTART.md)를 참조하세요!

## 📋 목차

- [환경 요구사항](#환경-요구사항)
- [설치 방법](#설치-방법)
- [Flink 클러스터 실행](#flink-클러스터-실행)
  - [Docker로 실행 (권장)](#docker로-실행-권장)
  - [로컬 바이너리로 실행](#로컬-바이너리로-실행)
- [예제](#예제)
  - [Fraud Detection Job](#1-fraud-detection-job-사기-거래-감지)
  - [Word Count](#2-word-count)
  - [Stream Source](#3-stream-source)
- [개발 가이드](#개발-가이드)
- [프로젝트 구조](#프로젝트-구조)

## 🔧 환경 요구사항

- Python 3.11 이상
- Poetry 1.8.0 이상
- Docker 및 Docker Compose (Docker 실행 방식 사용 시)
- Java 11 (로컬 바이너리 실행 시)

## 📦 설치 방법

### 1. Poetry 의존성 설치

```bash
# Poetry가 설치되어 있지 않다면
curl -sSL https://install.python-poetry.org | python3 -

# 의존성 설치
poetry install
```

### 2. 가상환경 활성화

```bash
poetry shell
```

## 🚀 Flink 클러스터 실행

### Docker로 실행 (권장)

Docker Compose를 사용하여 Flink 클러스터를 쉽게 시작할 수 있습니다.

```bash
# Flink 클러스터 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 클러스터 중지
docker-compose down
```

**Flink Web UI 접속**: http://localhost:8081

### 로컬 바이너리로 실행

로컬에서 Flink 바이너리를 직접 다운로드하여 실행할 수 있습니다.

#### 1. Flink 다운로드

```bash
./scripts/download-flink.sh
```

이 스크립트는 Apache Flink 2.1.0을 다운로드하고 압축을 해제합니다.

#### 2. Flink 클러스터 시작

```bash
./scripts/start-flink-local.sh
```

#### 3. Flink 클러스터 중지

```bash
./scripts/stop-flink-local.sh
```

**Flink Web UI 접속**: http://localhost:8081

## 📚 예제

### 1. Fraud Detection Job (사기 거래 감지)

실시간 사기 거래 패턴을 감지하는 스트림 처리 예제입니다.

**패턴**: 소액 거래(≤ $1.00) 후 1분 내 고액 거래(≥ $500.00) 발생 시 경고

```bash
# 실행
make fraud-run

# 또는
poetry run python examples/fraud_detection_job.py
```

**기술 스택**:
- KeyedProcessFunction (상태 기반 처리)
- ValueState (계정별 상태 관리)
- Event Time Timer (시간 기반 처리)

자세한 내용은 [Fraud Detection 가이드](docs/fraud_detection_guide.md)를 참조하세요.

### 2. Word Count

기본적인 단어 카운팅 예제입니다.

```bash
make word-count
```

### 3. Stream Source

다양한 데이터 소스 사용 예제입니다.

```bash
make stream-source
```

## 💻 개발 가이드

### 코드 포맷팅

```bash
# Black으로 코드 포맷팅
poetry run black src/ tests/

# Ruff로 린트 검사
poetry run ruff check src/ tests/

# Ruff로 자동 수정
poetry run ruff check --fix src/ tests/
```

### 타입 체크

```bash
poetry run mypy src/
```

### 테스트 실행

```bash
# 모든 테스트 실행
poetry run pytest

# 커버리지 포함
poetry run pytest --cov=src/pyflink_examples --cov-report=html

# 특정 테스트 파일만 실행
poetry run pytest tests/test_example.py
```

## 📁 프로젝트 구조

```
apache-flink-practices/
├── src/
│   └── pyflink_examples/           # PyFlink 예제 코드
│       ├── __init__.py
│       └── fraud_detection/        # 사기 거래 감지 예제
│           ├── __init__.py
│           ├── entities.py         # Transaction, Alert 엔티티
│           ├── fraud_detector.py   # FraudDetector 프로세서
│           └── job.py             # Job 구성
├── tests/                          # 테스트 코드
│   ├── __init__.py
│   └── test_fraud_detection.py    # Fraud Detection 테스트
├── examples/                       # 실행 가능한 예제 스크립트
│   ├── fraud_detection_job.py     # 사기 거래 감지 Job
│   ├── word_count.py              # 단어 카운팅
│   └── stream_source_example.py   # 스트림 소스 예제
├── scripts/                        # 유틸리티 스크립트
│   ├── download-flink.sh          # Flink 다운로드
│   ├── start-flink-local.sh       # Flink 시작
│   ├── stop-flink-local.sh        # Flink 중지
│   └── wait-for-flink.sh          # 클러스터 준비 대기
├── docs/                           # 문서
│   ├── overview.md
│   ├── DataStream API 첫걸음.md
│   └── fraud_detection_guide.md   # Fraud Detection 가이드
├── docker-compose.yml              # Docker Compose 설정
├── pyproject.toml                  # Poetry 의존성 및 도구 설정
├── Makefile                        # 개발 편의 명령어
└── README.md
```

## 🎓 학습 자료

- [Apache Flink 공식 문서](https://flink.apache.org/docs/stable/)
- [PyFlink API 문서](https://nightlies.apache.org/flink/flink-docs-release-2.1/)
- [Flink DataStream API](https://nightlies.apache.org/flink/flink-docs-release-2.1/docs/dev/datastream/overview/)

## 📝 주요 개념

### Flink의 핵심 4가지 개념

1. **연속적 스트림 처리**: 무한 데이터 스트림을 실시간으로 처리
2. **이벤트 시간**: 데이터가 실제로 발생한 시간을 기준으로 처리
3. **상태 저장 처리**: 이벤트 처리 중 상태를 유지하고 관리
4. **내결함성**: 체크포인트와 상태 스냅샷을 통한 장애 복구

### Flink 애플리케이션 구조

```
Source → Operator → Operator → ... → Sink
```

- **Source**: 데이터 입력 (Kafka, 파일, 소켓 등)
- **Operator**: 데이터 변환 (map, filter, window 등)
- **Sink**: 데이터 출력 (데이터베이스, 파일, Kafka 등)

## 🔗 관련 링크

- [Apache Flink 공식 사이트](https://flink.apache.org/)
- [Flink Docker Hub](https://hub.docker.com/_/flink)
- [PyFlink GitHub](https://github.com/apache/flink/tree/master/flink-python)

## 📄 라이선스

이 프로젝트는 학습 목적으로 작성되었습니다.


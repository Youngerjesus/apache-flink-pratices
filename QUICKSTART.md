# 빠른 시작 가이드

## 1️⃣ 의존성 설치

```bash
# Poetry 설치 (이미 설치되어 있다면 생략)
curl -sSL https://install.python-poetry.org | python3 -

# 프로젝트 의존성 설치
poetry install

# 가상환경 활성화
poetry shell
```

## 2️⃣ Flink 클러스터 실행

### 방법 1: Docker 사용 (권장)

```bash
# Flink 클러스터 시작
make docker-up
# 또는
docker-compose up -d

# 클러스터가 준비될 때까지 대기 (권장)
make docker-wait

# Web UI 확인
# 브라우저에서 http://localhost:8081 접속
```

> ⚠️ **참고**: 클러스터 시작 직후 Web UI에 접속하면 "Service temporarily unavailable due to an ongoing leader election" 메시지가 나타날 수 있습니다. 이는 정상이며, 10-15초 후 새로고침하면 해결됩니다.

### 방법 2: 로컬 바이너리 사용

```bash
# Flink 다운로드 (최초 1회)
make flink-download

# Flink 클러스터 시작
make flink-start

# Web UI 확인
# 브라우저에서 http://localhost:8081 접속
```

## 3️⃣ 예제 실행

```bash
# Word Count 예제 실행
poetry run python examples/word_count.py

# Stream Source 예제 실행
poetry run python examples/stream_source_example.py
```

## 4️⃣ 개발 도구 사용

```bash
# 코드 포맷팅
make format

# 린트 검사
make lint

# 타입 체크
make typecheck

# 테스트 실행
make test
```

## 5️⃣ 정리

```bash
# Docker 클러스터 중지
make docker-down

# 또는 로컬 바이너리 클러스터 중지
make flink-stop

# 캐시 파일 정리
make clean
```

## 🔧 트러블슈팅

### Java 버전 확인 (로컬 바이너리 사용 시)

```bash
java -version
# Java 11 이상이어야 합니다
```

### Docker 실행 확인

```bash
docker --version
docker-compose --version
```

### "leader election" 메시지

클러스터 시작 직후 나타나는 정상적인 메시지입니다:
```
{"errors":["Service temporarily unavailable due to an ongoing leader election. Please refresh."]}
```

**해결 방법**:
```bash
# 준비 상태 대기
make docker-wait

# 또는 10-15초 후 브라우저 새로고침
```

### Flink Web UI 접속 불가

1. 클러스터가 시작되었는지 확인
   ```bash
   # Docker 사용 시
   docker-compose ps
   
   # 준비 상태 확인
   make docker-wait
   
   # 로컬 바이너리 사용 시
   curl http://localhost:8081
   ```

2. 포트 8081이 이미 사용 중인지 확인
   ```bash
   lsof -i :8081
   ```

3. 로그 확인
   ```bash
   # Docker
   docker-compose logs jobmanager
   
   # 로컬
   cat flink-2.1.0/log/*.log
   ```

## 📚 다음 단계

- `docs/overview.md` - Flink 개념 학습
- `docs/DataStream API 첫걸음.md` - DataStream API 이해
- `examples/` - 더 많은 예제 탐색


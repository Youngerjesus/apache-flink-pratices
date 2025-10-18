.PHONY: help install format lint test clean docker-up docker-down flink-download flink-start flink-stop fraud-run fraud-submit word-count stream-source

help:
	@echo "Apache Flink Practices - 사용 가능한 명령어:"
	@echo ""
	@echo "  make install          - Poetry 의존성 설치"
	@echo "  make format           - 코드 포맷팅 (black)"
	@echo "  make lint             - 코드 린트 (ruff)"
	@echo "  make typecheck        - 타입 체크 (mypy)"
	@echo "  make test             - 테스트 실행"
	@echo "  make test-cov         - 커버리지 포함 테스트"
	@echo "  make clean            - 캐시 및 빌드 파일 정리"
	@echo ""
	@echo "  make docker-up        - Docker Flink 클러스터 시작"
	@echo "  make docker-wait      - Flink 클러스터 준비 대기"
	@echo "  make docker-down      - Docker Flink 클러스터 중지"
	@echo "  make docker-logs      - Docker 로그 확인"
	@echo ""
	@echo "  make flink-download   - Flink 바이너리 다운로드"
	@echo "  make flink-start      - 로컬 Flink 클러스터 시작"
	@echo "  make flink-stop       - 로컬 Flink 클러스터 중지"
	@echo ""
	@echo "예제 실행:"
	@echo "  make fraud-run        - Fraud Detection Job 로컬 실행"
	@echo "  make fraud-submit     - Fraud Detection Job 클러스터 제출"
	@echo "  make word-count       - Word Count 예제 실행"
	@echo "  make stream-source    - Stream Source 예제 실행"
	@echo ""

install:
	poetry install

format:
	poetry run black src/ tests/ examples/
	poetry run ruff check --fix src/ tests/ examples/

lint:
	poetry run ruff check src/ tests/ examples/

typecheck:
	poetry run mypy src/

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=src/pyflink_examples --cov-report=html --cov-report=term

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/

docker-up:
	docker-compose up -d
	@echo ""
	@echo "Flink 클러스터가 시작되는 중입니다..."
	@echo "준비 상태를 확인하려면: make docker-wait"
	@echo ""
	@echo "Flink Web UI: http://localhost:8081"

docker-wait:
	./scripts/wait-for-flink.sh

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

flink-download:
	./scripts/download-flink.sh

flink-start:
	./scripts/start-flink-local.sh

flink-stop:
	./scripts/stop-flink-local.sh

# 예제 실행
fraud-run:
	@echo "=================================="
	@echo "Fraud Detection Job 로컬 실행"
	@echo "=================================="
	@echo ""
	poetry run python examples/fraud_detection_job.py

fraud-submit:
	@echo "=================================="
	@echo "Fraud Detection Job 클러스터 제출"
	@echo "=================================="
	@echo ""
	./scripts/submit-fraud-detection.sh

word-count:
	@echo "=================================="
	@echo "Word Count 예제 실행"
	@echo "=================================="
	@echo ""
	poetry run python examples/word_count.py

stream-source:
	@echo "=================================="
	@echo "Stream Source 예제 실행"
	@echo "=================================="
	@echo ""
	poetry run python examples/stream_source_example.py


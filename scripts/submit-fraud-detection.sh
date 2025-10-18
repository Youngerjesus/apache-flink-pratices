#!/bin/bash

# Fraud Detection Job을 Docker Flink 클러스터에 제출하는 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================="
echo "Fraud Detection Job을 Flink 클러스터에 제출"
echo "=================================="
echo ""

# Docker 클러스터가 실행 중인지 확인
if ! docker-compose ps | grep -q "flink-jobmanager.*Up"; then
    echo "❌ Flink 클러스터가 실행 중이지 않습니다."
    echo "다음 명령어로 클러스터를 시작하세요:"
    echo "  make docker-up && make docker-wait"
    exit 1
fi

echo "✅ Flink 클러스터 확인됨"
echo ""

# Python 파일을 Docker 컨테이너에 복사
echo "📦 Job 파일을 컨테이너에 복사 중..."
docker cp "$PROJECT_ROOT/src" flink-jobmanager:/opt/flink/
docker cp "$PROJECT_ROOT/examples" flink-jobmanager:/opt/flink/

echo "✅ 파일 복사 완료"
echo ""

# Job 제출
echo "🚀 Job 제출 중..."
docker exec flink-jobmanager /opt/flink/bin/flink run \
    --jobmanager localhost:8081 \
    --python /opt/flink/examples/fraud_detection_job.py \
    --pyFiles /opt/flink/src/pyflink_examples \
    --detached

echo ""
echo "✅ Job이 클러스터에 제출되었습니다!"
echo ""
echo "📊 Web UI에서 확인하세요: http://localhost:8081"
echo ""


#!/bin/bash

# Flink 로컬 클러스터 시작 스크립트

set -e

FLINK_VERSION="2.1.0"
FLINK_DIR="flink-${FLINK_VERSION}"

echo "================================================"
echo "Flink 로컬 클러스터 시작"
echo "================================================"

# Flink 설치 확인
if [ ! -d "${FLINK_DIR}" ]; then
    echo "❌ Flink가 설치되어 있지 않습니다."
    echo ""
    echo "먼저 Flink를 다운로드하세요:"
    echo "  ./scripts/download-flink.sh"
    exit 1
fi

# 이미 실행 중인지 확인
if [ -f "${FLINK_DIR}/bin/../log/flink-*-standalonesession-*.log" ]; then
    if pgrep -f "org.apache.flink.runtime.entrypoint.StandaloneSessionClusterEntrypoint" > /dev/null; then
        echo "⚠ Flink 클러스터가 이미 실행 중입니다."
        echo ""
        echo "Web UI: http://localhost:8081"
        exit 0
    fi
fi

# Flink 클러스터 시작
echo "Flink 클러스터를 시작합니다..."
cd "${FLINK_DIR}"
./bin/start-cluster.sh
cd ..

echo ""
echo "✓ Flink 클러스터가 시작되었습니다!"
echo ""
echo "================================================"
echo "Flink Web UI: http://localhost:8081"
echo "================================================"
echo ""
echo "클러스터를 중지하려면:"
echo "  ./scripts/stop-flink-local.sh"
echo ""

# 상태 확인 (3초 대기 후)
sleep 3
if curl -s http://localhost:8081 > /dev/null 2>&1; then
    echo "✓ JobManager가 정상적으로 실행 중입니다."
else
    echo "⚠ JobManager가 아직 시작되지 않았습니다. 잠시 후 다시 확인하세요."
fi


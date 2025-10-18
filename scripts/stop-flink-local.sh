#!/bin/bash

# Flink 로컬 클러스터 중지 스크립트

set -e

FLINK_VERSION="2.1.0"
FLINK_DIR="flink-${FLINK_VERSION}"

echo "================================================"
echo "Flink 로컬 클러스터 중지"
echo "================================================"

# Flink 설치 확인
if [ ! -d "${FLINK_DIR}" ]; then
    echo "❌ Flink가 설치되어 있지 않습니다."
    exit 1
fi

# 실행 중인지 확인
if ! pgrep -f "org.apache.flink.runtime.entrypoint.StandaloneSessionClusterEntrypoint" > /dev/null; then
    echo "⚠ Flink 클러스터가 실행 중이지 않습니다."
    exit 0
fi

# Flink 클러스터 중지
echo "Flink 클러스터를 중지합니다..."
cd "${FLINK_DIR}"
./bin/stop-cluster.sh
cd ..

echo ""
echo "✓ Flink 클러스터가 중지되었습니다."
echo ""


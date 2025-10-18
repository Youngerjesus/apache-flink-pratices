#!/bin/bash

# Flink 바이너리 다운로드 및 설치 스크립트
# Apache Flink 2.1.0을 로컬에 다운로드합니다.

set -e

FLINK_VERSION="2.1.0"
SCALA_VERSION="2.12"
FLINK_DIR="flink-${FLINK_VERSION}"
FLINK_PACKAGE="flink-${FLINK_VERSION}-bin-scala_${SCALA_VERSION}.tgz"
DOWNLOAD_URL="https://archive.apache.org/dist/flink/flink-${FLINK_VERSION}/${FLINK_PACKAGE}"

echo "================================================"
echo "Apache Flink ${FLINK_VERSION} 다운로드 시작"
echo "================================================"

# 이미 설치되어 있는지 확인
if [ -d "${FLINK_DIR}" ]; then
    echo "✓ Flink ${FLINK_VERSION}이 이미 설치되어 있습니다."
    echo "  위치: $(pwd)/${FLINK_DIR}"
    echo ""
    echo "재설치하려면 먼저 기존 디렉토리를 삭제하세요:"
    echo "  rm -rf ${FLINK_DIR} ${FLINK_PACKAGE}"
    exit 0
fi

# 다운로드
echo "다운로드 중: ${DOWNLOAD_URL}"
if ! curl -L -O "${DOWNLOAD_URL}"; then
    echo "❌ 다운로드 실패!"
    exit 1
fi

echo "✓ 다운로드 완료"

# 압축 해제
echo "압축 해제 중..."
if ! tar -xzf "${FLINK_PACKAGE}"; then
    echo "❌ 압축 해제 실패!"
    exit 1
fi

echo "✓ 압축 해제 완료"

# 다운로드 파일 삭제
echo "임시 파일 정리 중..."
rm "${FLINK_PACKAGE}"

echo ""
echo "================================================"
echo "✓ Flink ${FLINK_VERSION} 설치 완료!"
echo "================================================"
echo ""
echo "설치 위치: $(pwd)/${FLINK_DIR}"
echo ""
echo "다음 명령어로 Flink 클러스터를 시작할 수 있습니다:"
echo "  ./scripts/start-flink-local.sh"
echo ""
echo "또는 직접:"
echo "  ./${FLINK_DIR}/bin/start-cluster.sh"
echo ""


#!/bin/bash

# PyFlink 프로젝트 초기 설정 스크립트

set -e

echo "================================================"
echo "PyFlink 프로젝트 초기 설정"
echo "================================================"
echo ""

# Poetry 설치 확인
if ! command -v poetry &> /dev/null; then
    echo "Poetry가 설치되어 있지 않습니다."
    echo "Poetry를 설치하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Poetry 설치 중..."
        curl -sSL https://install.python-poetry.org | python3 -
        echo "✓ Poetry 설치 완료"
    else
        echo "Poetry 설치가 필요합니다: https://python-poetry.org/docs/#installation"
        exit 1
    fi
fi

# Poetry 의존성 설치
echo ""
echo "의존성 설치 중..."
poetry install

echo ""
echo "✓ 의존성 설치 완료"

# Docker 설치 확인
echo ""
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "✓ Docker 및 Docker Compose가 설치되어 있습니다."
    echo ""
    echo "Docker로 Flink 클러스터를 시작하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Flink 클러스터 시작 중..."
        docker-compose up -d
        echo ""
        echo "✓ Flink 클러스터가 시작되었습니다!"
        echo "  Web UI: http://localhost:8081"
    fi
else
    echo "⚠ Docker가 설치되어 있지 않습니다."
    echo "  Docker 설치: https://docs.docker.com/get-docker/"
    echo ""
    echo "로컬 바이너리로 Flink를 다운로드하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        ./scripts/download-flink.sh
    fi
fi

echo ""
echo "================================================"
echo "✓ 설정 완료!"
echo "================================================"
echo ""
echo "다음 명령어로 시작하세요:"
echo ""
echo "  poetry shell              # 가상환경 활성화"
echo "  make help                 # 사용 가능한 명령어 보기"
echo "  make docker-up            # Docker로 Flink 시작"
echo ""
echo "예제 실행:"
echo "  poetry run python examples/word_count.py"
echo ""


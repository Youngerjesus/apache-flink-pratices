#!/bin/bash

# Flink 클러스터가 준비될 때까지 대기하는 스크립트

set -e

MAX_WAIT=60  # 최대 대기 시간 (초)
INTERVAL=2   # 체크 간격 (초)
ELAPSED=0

echo "================================================"
echo "Flink 클러스터 준비 상태 확인 중..."
echo "================================================"
echo ""

# Docker Compose 사용 여부 확인
if command -v docker-compose &> /dev/null; then
    USE_DOCKER=true
else
    USE_DOCKER=false
fi

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # HTTP 상태 코드 확인
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/config 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Flink 클러스터가 준비되었습니다!"
        echo ""
        echo "================================================"
        echo "Flink Web UI: http://localhost:8081"
        echo "================================================"
        echo ""
        
        # 클러스터 정보 출력
        if [ "$USE_DOCKER" = true ]; then
            echo "실행 중인 컨테이너:"
            docker-compose ps
        fi
        
        exit 0
    else
        if [ "$HTTP_CODE" = "503" ]; then
            echo "⏳ 리더 선출 진행 중... (${ELAPSED}초 경과)"
        elif [ "$HTTP_CODE" = "000" ]; then
            echo "⏳ JobManager 시작 대기 중... (${ELAPSED}초 경과)"
        else
            echo "⏳ 준비 중... (HTTP $HTTP_CODE, ${ELAPSED}초 경과)"
        fi
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo ""
echo "❌ 타임아웃: Flink 클러스터가 ${MAX_WAIT}초 내에 준비되지 않았습니다."
echo ""
echo "문제 해결을 위해 다음을 시도해보세요:"
echo ""

if [ "$USE_DOCKER" = true ]; then
    echo "1. 로그 확인:"
    echo "   docker-compose logs jobmanager"
    echo "   docker-compose logs taskmanager"
    echo ""
    echo "2. 클러스터 재시작:"
    echo "   docker-compose down && docker-compose up -d"
    echo ""
    echo "3. 포트 충돌 확인:"
    echo "   lsof -i :8081"
else
    echo "1. 로그 확인:"
    echo "   cat flink-2.1.0/log/*.log"
    echo ""
    echo "2. 클러스터 재시작:"
    echo "   ./scripts/stop-flink-local.sh && ./scripts/start-flink-local.sh"
fi

exit 1


#!/usr/bin/env python3
"""
Fraud Detection Job 실행 스크립트

실시간 사기 거래 감지 시스템을 실행합니다.

사용법:
    # 로컬 실행
    poetry run python examples/fraud_detection_job.py

    # Docker Flink 클러스터 사용 시
    1. make docker-up && make docker-wait
    2. poetry run python examples/fraud_detection_job.py
    3. http://localhost:8081 에서 Web UI 확인
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pyflink_examples.fraud_detection.job import run_fraud_detection_job


def main() -> None:
    """메인 함수"""
    try:
        run_fraud_detection_job()
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n오류 발생: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


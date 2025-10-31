#!/bin/bash
# Protobuf 스키마 파일 컴파일 스크립트
#
# 이 스크립트는 proto/ 디렉토리의 .proto 파일들을 Python 코드로 컴파일합니다.
# 생성된 파일들은 src/data_ingestion/infrastructure/proto_generated/ 디렉토리에 저장됩니다.

set -e  # 에러 발생 시 스크립트 중단

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.."

# 출력 디렉토리 생성
OUTPUT_DIR="src/data_ingestion/infrastructure/proto_generated"
mkdir -p "$OUTPUT_DIR"

# protoc 설치 확인
if ! command -v protoc &> /dev/null; then
    echo "❌ Error: protoc가 설치되어 있지 않습니다."
    echo "설치 방법 (macOS): brew install protobuf"
    echo "설치 방법 (Ubuntu): sudo apt-get install protobuf-compiler"
    exit 1
fi

echo "🔨 Protobuf 스키마 컴파일 시작..."

# .proto 파일 컴파일
protoc \
    --python_out="$OUTPUT_DIR" \
    --pyi_out="$OUTPUT_DIR" \
    --proto_path=proto \
    proto/*.proto

# __init__.py 생성
touch "$OUTPUT_DIR/__init__.py"

echo "✅ Protobuf 컴파일 완료!"
echo "생성된 파일 위치: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"



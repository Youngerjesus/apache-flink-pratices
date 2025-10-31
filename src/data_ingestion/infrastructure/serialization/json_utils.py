"""
고성능 JSON 유틸리티

orjson이 설치되어 있으면 우선 사용하고, 없으면 표준 json으로 폴백합니다.
웹소켓 I/O에 맞춰 dumps는 str(UTF-8)로 반환합니다.
"""

from __future__ import annotations

from typing import Any

import orjson 

def json_loads(data: Any) -> Any:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return orjson.loads(data)
    return orjson.loads(str(data).encode("utf-8"))

def json_dumps(obj: Any) -> str:
    # orjson.dumps → bytes 반환, websockets.send는 str를 기대
    return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS).decode("utf-8")

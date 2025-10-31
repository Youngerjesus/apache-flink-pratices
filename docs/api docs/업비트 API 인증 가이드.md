업비트의 거래 및 자산 관리 API를 사용하려면 API Key를 이용한 JWT (JSON Web Token) 인증이 반드시 필요합니다. 이는 REST API 호출과 WebSocket 연결 모두에 동일하게 적용됩니다.

### API Key
API 사용의 첫 단계는 API Key를 발급받고 올바르게 설정하는 것입니다.
- 구조: API Key는 Access Key (공개)와 Secret Key (비공개) 한 쌍으로 구성됩니다. Secret Key는 발급 시에만 확인 가능하므로 안전하게 보관해야 합니다.
- IP 등록: API를 호출하려는 기기의 IP 주소를 허용 목록에 등록해야 합니다. 키 하나당 최대 10개의 IP를 등록할 수 있습니다.
- 권한 그룹: Key 발급 시, 보안을 위해 필요한 기능에만 선택적으로 권한을 부여할 수 있습니다.
    - 자산 조회: 계좌 잔고 조회 등
    - 주문하기: 매수/매도 주문 생성 및 취소
    - 주문 조회: 주문 내역 및 상태 조회
    - 출금/입금 관련: 디지털 자산 및 원화의 입출금과 조회

### 인증 토큰 (JWT)
모든 인증 요청에는 JWT 토큰이 필요합니다. 이 토큰은 사용자의 신원과 권한을 증명하는 역할을 합니다.

JWT 구조
- JWT는 헤더(Header).페이로드(Payload).서명(Signature) 세 부분으로 구성됩니다.

- 헤더 (Header): 토큰 서명에 사용된 암호화 알고리즘 정보(HS512 권장)를 포함합니다.

- 페이로드 (Payload): 인증의 핵심 내용이 담깁니다.
    - access_key: 본인의 Access Key
    - nonce: 요청마다 생성하는 고유한 값 (UUID 권장)
    - query_hash: 요청 파라미터가 있을 경우에만 필수이며, 파라미터를 해시(SHA512)한 값입니다.
    - query_hash_alg: query_hash 생성에 사용된 알고리즘 (SHA512가 기본값)

- 서명 (Signature): 헤더와 페이로드를 Secret Key를 이용해 암호화한 값입니다.
    -  Secret Key는 Base64 인코딩 되어있지 않습니다.
    - JWT 토큰의 서명 데이터 생성 시 키 사용을 위해 별도의 Base64 디코딩을 수행할 필요가 없습니다. JWT 생성을 위한 라이브러리 사용 시 해당 옵션을 참고하여 구현하시기 바랍니다.

### query_hash 생성 방법

요청 내용과 토큰의 내용이 일치해야 하므로 정확한 query_hash 생성이 중요합니다.

- GET, DELETE 요청: URL의 쿼리 스트링(? 뒷부분)을 순서 변경 없이 그대로 해시합니다.
    - 예시: /v1/orders/open?market=KRW-BTC&limit=10 요청 시, market=KRW-BTC&limit=10 문자열을 해시.

- POST 요청: JSON 형식의 요청 본문(Body)을 쿼리 스트링 형식(key=value&key2=value2)으로 변환한 후 해시합니다.
    - 예시: {"market":"KRW-BTC", "side":"bid"} 본문은 market=KRW-BTC&side=bid 문자열로 변환하여 해시.

### 토큰 전송

생성된 JWT 토큰은 요청 헤더의 Authorization 필드에 아래와 같은 형식으로 전송합니다.

Key: Authorization

Value: Bearer {생성된 JWT 토큰}

### 코드 예시

API 문서에는 실제 개발에 참고할 수 있도록 주요 언어별 코드 예시가 포함되어 있습니다.
- 지원 언어: Python, Java, JavaScript
- 제공 예시:
    - REST API 호출 (파라미터가 있는 경우/없는 경우, GET/POST)
    - WebSocket 연결 요청

#### REST API 예시 
```python
import jwt # PyJWT
import requests

def _build_query_string(params: Dict[str, Any]) -> str:
    return unquote(urlencode(params, doseq=True))

def _create_jwt(access_key: str, secret_key: str, query_string: str = "") -> str:
    payload = {"access_key": access_key, "nonce": str(uuid.uuid4())}

    if query_string:
        query_hash = hashlib.sha512(query_string.encode("utf-8")).hexdigest()
        payload["query_hash"] = query_hash
        payload["query_hash_alg"] = "SHA512"

    token = jwt.encode(payload, secret_key, algorithm="HS512")
    return token if isinstance(token, str) else token.decode('utf-8')  

if __name__ == "__main__":
    base_url = "https://api.upbit.com"
    access_key = "YOUR_ACCESS_KEY"
    secret_key = "YOUR_SECRET_KEY" # 실제로는 안전한 방식으로 로드하거나 주입하세요.
    
    # 파라미터가 없는 요청 예시
    jwt_token = _create_jwt(access_key, secret_key)
    headers = {"Authorization": f"Bearer {jwt_token}"}
                
    response = requests.get(f"{base_url}/v1/accounts", headers=headers)
        
    print(response.json())
    
    # 파라미터가 있는 GET 요청 예시
    params = {
        "market": "KRW-BTC",
        "states[]": ["wait", "watch"],
        "limit": 10
    }
    query_string = _build_query_string(params)
    jwt_token = _create_jwt(access_key, secret_key, query_string)
    headers = {"Authorization": f"Bearer {jwt_token}"}
        
    response = requests.get(f"{base_url}/v1/orders/open?{query_string}", headers=headers)
    print(response.json())    
    
    # POST 요청 예시
    order_data = {
        "market": "KRW-BTC",
        "side": "bid",
        "volume": "0.001",
        "price": "50000000",
        "ord_type": "limit"
    }
        
    query_string = _build_query_string(order_data)
    jwt_token = _create_jwt(access_key, secret_key, query_string)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    # 아래 주석처리된 부분 실행시 실제 주문이 발생하므로 실행 전 반드시 확인하세요.
    # response = requests.post(f"{base_url}/v1/orders", json=order_data, headers=headers)
    # print(response.json())     

```

#### Websocket 예시: 

```python
import jwt  # PyJWT
import uuid
import websocket  # websocket-client

def on_message(ws, message):
    # do something
    data = message.decode('utf-8')
    print(data)


def on_connect(ws):
    print("connected!")
    # Request after connection
    ws.send('[{"ticket":"test example"},{"type":"myOrder"}]')


def on_error(ws, err):
    print(err)


def on_close(ws, status_code, msg):
  print("closed!")

payload = {
    'access_key': "YOUR_ACCESS_KEY",
    'nonce': str(uuid.uuid4()),
}

jwt_token = jwt.encode(payload, "YOUR_SECRET_KEY");
authorization_token = 'Bearer {}'.format(jwt_token)
headers = {"Authorization": authorization_token}

ws_app = websocket.WebSocketApp("wss://api.upbit.com/websocket/v1/private",
                                header=headers,
                                on_message=on_message,
                                on_open=on_connect,
                                on_error=on_error,
                                on_close=on_close)
ws_app.run_forever()
```
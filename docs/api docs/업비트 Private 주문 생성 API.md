# 주문 생성
 
POST / https://api.upbit.com/v1/orders

## 주문 유형(ord_type)

사용 가능한 주문 유형은 다음과 같습니다.

### 지정가 주문 

지정가 주문은 사용자가 직접 설정한 매수/매도 단가, 또는 더 유리한 가격에 호가가 도달한 경우에만 체결되는 주문 유형입니다. 체결 단가의 상한/하한을 통제할 수 있지만, 시장 가격이 지정한 단가에 도달하지 않을 수 있으므로 체결을 보장할 수 없습니다.

아래 표를 참고하여 지정가 매수/매도 주문 생성 요청 시 사용 가능한 파라미터를 쉽게 확인할 수 있습니다. 각 파라미터에 대한 상세한 설명은 하단 Request Body를 참고해주세요.
파라미터	필수 여부	설명
market	Required	페어 코드. KRW-BTC 형식으로 입력합니다.
side	Required	매수시 bid, 매도시 ask로 입력합니다.
ord_type	Required	limit
volume	Required	주문 수량. 0.1 입력시 지정가로 0.1개의 자산을 매수/매도합니다.
price	Required	호가 자산 기준 주문 단가. 예를 들어, KRW-BTC 페어에서 BTC 1개당 1억원(KRW)으로 매수/매도하는 경우 100000000을 입력합니다.
time_in_force	Optional	ioc,fok,post_only
post_only 옵션은 smp_type 옵션과 함께 사용할 수 없습니다.
smp_type	Optional	자전거래 체결 방지 옵션. cancel_maker,cancel_taker,reduce
identifier	Optional	

---

### 시장가 주문

시장가 주문은 현재 시장에서 가장 유리한 가격으로 즉시 체결되는 주문 유형입니다. 빠른 체결이 보장되지만, 시장 상황에 따라 체결 가격이 변동될 수 있습니다.

#### 시장가 매수 주문 생성 요청 파라미터 사용 예시

아래 표를 참고하여 시장가 매수 주문 생성 요청 시 사용 가능한 파라미터를 쉽게 확인할 수 있습니다. volume 파라미터를 입력하지 않습니다(value에 null로 입력 또는 key 자체를 제외). 각 파라미터에 대한 상세한 설명은 하단 Request Body를 참고해주세요.

파라미터	필수 여부	설명
market	Required	페어 코드. KRW-BTC 형식으로 입력합니다.
side	Required	bid
ord_type	Required	price
price	Required	호가 자산 기준 주문 총액. 예를 들어, KRW-BTC 페어에서 100000000을 입력하는 경우 시장가로 1억 원어치의 BTC 수량이 매수됩니다.
smp_type	Optional	자전거래 체결 방지 옵션. cancel_maker,cancel_taker,reduce
identifier	Optional	조회, 삭제시 사용할 수 있는 사용자 지정 주문 ID.

#### 시장가 매도 주문 생성 요청 파라미터 사용 예시

아래 표를 참고하여 시장가 매도 주문 생성 요청 시 사용 가능한 파라미터를 쉽게 확인할 수 있습니다. price 파라미터를 입력하지 않습니다(value에 null로 입력 또는 key 자체를 제외). 각 파라미터에 대한 상세한 설명은 하단 Request Body를 참고해주세요.

파라미터	필수 여부	설명
market	Required	페어 코드. KRW-BTC 형식으로 입력합니다.
side	Required	ask
ord_type	Required	market
volume	Required	매도 주문 수량. 예를 들어, KRW-BTC 페어에서 0.1을 입력하는 경우 시장가로 0.1개의 BTC 수량이 매도됩니다.
smp_type	Optional	자전거래 체결 방지 옵션. cancel_maker,cancel_taker,reduce
identifier	Optional	조회, 삭제시 사용할 수 있는 사용자 지정 주문 ID.

--- 

### 최유리 지정가 주문

최유리 지정가 주문은 현재 시장에서 가장 유리한 상대 호가를 가격으로 하는 주문 유형입니다. 전량 체결을 항상 보장할 수는 없으나, 빠르게 유리한 가격으로 호가창에 진입하고 싶은 경우 유용합니다.

#### 최유리지정가 매수 주문 생성 요청 파라미터 사용 예시

아래 표를 참고하여 최유리지정가 매수 주문 생성 요청 시 사용 가능한 파라미터를 쉽게 확인할 수 있습니다. volume 파라미터를 입력하지 않습니다(value에 null로 입력 또는 key 자체를 제외). 각 파라미터에 대한 상세한 설명은 하단 Request Body를 참고해주세요.

파라미터	필수 여부	설명
market	Required	페어 코드. KRW-BTC 형식으로 입력합니다.
side	Required	bid
ord_type	Required	best
price	Required	호가 자산 기준 주문 총액. 최유리 호가로 주문 총액에 해당하는 수량을 매수하는 주문이 생성됩니다. 예를 들어, KRW-BTC 페어에서 100000000을 입력하는 경우 최유리 호가로 1억 원어치의 BTC 수량을 매수하는 주문이 생성됩니다.
time_in_force	Required	ioc,fok
smp_type	Optional	자전거래 체결 방지 옵션. cancel_maker,cancel_taker,reduce
identifier	Optional	조회, 삭제시 사용할 수 있는 사용자 지정 주문 ID.

#### 최유리지정가 매도 주문 생성 요청 파라미터 사용 예시

아래 표를 참고하여 최유리지정가 매도 주문 생성 요청 시 사용 가능한 파라미터를 쉽게 확인할 수 있습니다. price 파라미터를 입력하지 않습니다(value에 null로 입력 또는 key 자체를 제외). 각 파라미터에 대한 상세한 설명은 하단 Request Body를 참고해주세요.

파라미터	필수 여부	설명
market	Required	페어 코드. KRW-BTC 형식으로 입력합니다.
side	Required	ask
ord_type	Required	best
volume	Required	매도 주문 수량. 예를 들어, KRW-BTC 페어에서 0.1을 입력하는 경우 최유리 호가로 0.1개의 BTC 수량을 매도하는 주문이 생성됩니다.
time_in_force	Required	ioc,fok
smp_type	Optional	자전거래 체결 방지 옵션. cancel_maker,cancel_taker,reduce
identifier	Optional	조회, 삭제시 사용할 수 있는 사용자 지정 주문 ID.

---

### 주문 체결 조건(time_in_force)

주문 옵션으로, 주문 생성 시점의 체결 상황에 따른 주문 처리 방식을 지정할 수 있습니다.

사용 가능한 주문 체결 조건(time_in_force) 옵션

옵션	파라미터 값	설명
IOC(Immediate or Cancel)	ioc	지정가 조건으로 즉시 체결 가능한 수량만 부분 체결하고, 잔여 수량은 취소합니다. 지정가 주문과 최유리 지정가 주문 에서 사용 가능한 옵션입니다.
FOK(Fill or Kill)	fok	지정가 조건으로 주문량 전량 체결 가능할 때만 주문을 실행하고, 아닌 경우 전량 주문 취소합니다. 지정가 주문과 최유리 지정가 주문 에서 사용 가능한 옵션입니다.
Post Only	post_only	지정가 조건으로 부분 또는 전체에 대해 즉시 체결 가능한 상황인 경우 주문을 실행하지 않고 취소합니다. 즉, 메이커(maker)주문으로 생성될 수 있는 상황에서만 주문이 생성되며 테이커(taker) 주문으로 체결되는 것을 방지합니다. 지정가 주문(ord_type이 limit)에서만 사용 가능한 옵션입니다. 자전 거래 체결 방지 옵션과 함께 사용할 수 없습니다.

---

### 자전거래 체결 방지 옵션(SMP, Self-Matching Prevention)

smp_type 파라미터를 설정하여 자전거래 체결 방지 옵션을 원하는 모드로 활성화할 수 있습니다. 자전거래 체결 방지 기능과 관련된 자세한 사항은 자전거래 체결 방지(Self-Match Prevention, SMP) 페이지를 참고하시기 바랍니다.

#### 사용 가능한 자전 거래 체결 방지(SMP) 옵션

메이커(maker) 주문과 테이커(taker) 주문에 설정된 SMP 모드가 서로 상이한 경우 테이커 주문 모드에 따라 동작합니다.

주문 생성 시 설정한 SMP 모드에 따라 기존 주문 또는 신규 주문의 전체 또는 부분 취소되는 경우 취소된 주문 수량과 금액은 주문 생성 응답의 "prevented_volume"필드와 "prevented_locked" 필드로 반환됩니다.

옵션	파라미터 값	설명
메이커 주문 취소	cancel_maker	메이커 주문을 취소합니다. 즉, 새로운 주문 생성 시 자전 거래 조건이 성립하는 경우 이전에 생성한 주문을 취소하여 체결을 방지합니다.
테이커 주문 취소	cancel_taker	테이커 주문을 취소합니다. 즉, 새로운 주문 생성 시 자전 거래 조건이 성립하는 경우 새롭게 생성한 주문을 취소하여 체결을 방지합니다.
주문 수량 조정	reduce	새로운 주문 생성 시 자전 거래 조건이 성립하는 경우 기존 주문과 신규 주문의 주문 수량을 줄여 체결을 방지합니다. 잔량이 0인 경우 주문을 취소합니다.

---

### 체결 대기 중 자산 잠금

주문 생성시 해당 주문에 사용되는 호가 자산(매수 주문의 경우) 또는 기준 자산(매도 주문의 경우)이 즉시 잠금(locked) 상태로 전환되며, 다른 용도로 사용할 수 없게 됩니다. 이는 사용자의 잔고가 주문 체결 시점에도 유효하도록 보장하기 위한 동작이며 계정 잔고 조회API 를 호출하여 잠금 자산 현황을 확인할 수 있습니다. 자산 잠금은 아래 조건 중 하나가 충족될 때까지 유지됩니다.

주문이 전량 체결되는 경우
- 사용자 요청으로 주문이 취소되는 경우
- time_in_force 조건에 따라 주문이 만료되는 경우
- 예시 KRW-BTC 마켓에서 지정가 매수 주문을 생성할 경우, 지정한 KRW 금액이 체결 전까지 잠금 상태로 유지됩니다.

### 주문 가격 단위와 최소 주문 가능 금액

마켓(호가 자산)과 기준 자산 단가에 따라 주문 시 사용 가능한 주문 가격 단위와 최소 주문 금액이 상이합니다. 마켓별 호가 정책은 아래 가이드를 참고하시기 바랍니다.

최소 주문 가능 금액: 5,000 KRW

BTC 최소 주문 가능 금액: 0.00005 BTC

USDT 마켓 최소 주문 가능 금액 : 0.5 USDT

---

### 클라이언트 주문 식별자(identifier)

주문 생성시 업비트 시스템 내에서 해당 주문을 유일하게 식별하기 위해 구분하는 UUID와 별개로, 주문을 생성하는 사용자 클라이언트 측에서 해당 주문을 식별하기 위해 할당하는 유일 구분자입니다. 사용자가 정의한 고유한 주문 ID 체계로 주문을 관리(조회 및 취소)하고자 하는 경우 유용합니다. 각 주문에는 사용자 계정의 전체 주문 내에서 유일하게 식별되는 값을 할당해야 하며, 한번 사용한 identifier 값은 해당 주문의 생성, 체결 여부와 상관 없이 재사용할 수 없습니다.

#### Rate Limit

초당 최대 8회 호출할 수 있습니다. 계정단위로 측정되며 [주문 생성 그룹] 내에서 요청 가능 횟수를 공유합니다.

#### API Key Permission

인증이 필요한 API로, \[주문하기] 권한이 설정된 API Key를 사용해야 합니다.
권한 오류(out_of_scope) 오류가 발생한다면, API Key 관리 메뉴에서 권한 설정을 확인해주세요.

--- 

### Body Params

market / string / required
- 주문을 생성하고자 하는 대상 페어(거래쌍)

side / string / enum / required
- 주문 방향(매수/매도).
- 매수 주문을 생성하는 경우 “bid”, 매도 주문을 생성하는 경우 “ask”로 지정합니다.
- Allowed: ask, bid

volume / string 
- 주문 수량.
- 매수 또는 매도하고자 하는 수량을 숫자 형식의 String으로 입력합니다.
- 다음 주문 유형에 대해 필수로 입력되어야 합니다.
    - 지정가 매수/매도(ord_type 필드가 “limit”인 경우)
    - 시장가 매도(ord_type 필드가 “market”인 경우)
    - 최유리 지정가 매도(side 필드가 “ask”, ord_type 필드가 “best”인 경우)

price / string
- 주문 단가 또는 총액.
- 디지털 자산 구매에 사용되는 통화(KRW,BTC,USDT)를 기준으로, 숫자 형식의 String으로 입력합니다.
- 다음 주문 조건에 대해 필수로 입력합니다.
    - 지정가 매수/매도(ord_type 필드가 “limit”인 경우)
    - 시장가 매수(ord_type 필드가 “price”인 경우)
    - 최유리 지정가 매수(side필드가 “bid”, ord_type 필드가 “best”인 경우)
- price 필드는 주문 유형에 따라 다른 용도로 사용됩니다.
    - 지정가 주문시 매수/매도 호가로 사용됩니다.
    - 시장가 매수, 최유리 지정가 매수시 매수 총액을 설정하는 용도로 사용됩니다. 주문 시점의 시장가 또는 최유리 지정가로 price 총액을 채우는 수량만큼 매수 주문이 체결됩니다.

ord_type / string / enum / required
- 주문 유형.
- 생성하고자 하는 주문 유형에 따라 아래 값 중 하나를 입력합니다.
    - limit: 지정가 매수/매도 주문
    - price: 시장가 매수 주문
    - market: 시장가 매도 주문
    - best: 최유리 지정가 매수/매도 주문 (time_in_force 필드 설정 필수)
- Allowed: limit, price, market, best

identifier / string
- 클라이언트 지정 주문 식별자.
- 각 주문에는 사용자 계정의 전체 주문 내에서 유일하게 식별되는 값을 할당해야 하며, 한번 사용한 identifier 값은 해당 주문의 생성,체결 여부와 상관 없이 재사용할 수 없습니다.

time_in_force / string / enum
- 주문 체결 조건.
- IOC(Immediate or Cancel), FOK(Fill or Kill), Post Only와 같은 주문 체결 조건을 설정할 수 있습니다.
- 시장가 주문(ord_type 필드가 "limit")인 경우 모든 옵션을 선택적으로 사용할 수 있습니다. 최유리 지정가 주문(ord_type 필드가 “best”)인 경우 대해 "ioc" 또는 "fok" 중 하나를 필수로 입력합니다. 사용 가능한 값은 다음과 같습니다.
    - ioc: 지정가 조건으로 체결 가능한 수량만 즉시 부분 체결하고, 잔여 수량은 취소됩니다.
    - fok: 지정가 조건으로 주문량 전량 체결 가능할 때만 주문을 실행하고, 아닌 경우 전량 주문 취소합니다.
    - post_only: 지정가 조건으로 부분 또는 전체에 대해 즉시 체결 가능한 상황인 경우 주문을 실행하지 않고 취소합니다. 즉, 메이커(maker)주문으로 생성될 수 있는 상황에서만 주문이 생성되며 테이커(taker) 주문으로 체결되는 것을 방지합니다.
- Allowed: fok, ioc, post_only

smp_type / string / enum
- 자전거래 체결 방지(Self-Match Prevention) 모드.
- 사용 가능한 값은 다음과 같습니다.
    - cancel_maker: 메이커 주문(이전 주문)을 취소합니다.
    - cancel_taker: 테이커 주문(신규 주문)을 취소합니다.
    - reduce: 기존 주문과 신규 주문의 주문 수량을 줄여 체결을 방지합니다. 잔량이 0인 경우 주문을 취소합니다.
- Allowed: cancel_maker, cancel_taker, reduce

---

### Responses

#### 201 Object of created order 

market / string / required
- 페어(거래쌍)의 코드
- \[예시] "KRW-BTC"

uuid / string / required
- 주문의 유일 식별자

side / string / enum / required
- 주문 방향(매수/매도)
- ask, bid

ord_type / string / enum / required
- 주문 유형.
- limit, price, market, best

price / string
- 주문 단가 또는 총액
- 지정가 주문의 경우 단가, 시장가 매수 주문의 경우 매수 총액입니다.

state / string / enum / required
- 주문 상태
    - wait: 체결 대기
    - watch: 예약 주문 대기
    - done: 체결 완료
    - cancel: 주문 취소
- wait, watch, done, cancel

created_at / string / required
- 주문 생성 시각 (KST 기준)
- \[형식] yyyy-MM-ddTHH:mm:ss+09:00

volume / string
- 주문 요청 수량

remaining_volume / string / required
- 체결 후 남은 주문 양

executed_volume / string / required
- 체결된 양

reserved_fee / string / required
- 수수료로 예약된 비용

remaining_fee / string / required
- 남은 수수료

paid_fee / string / required
- 사용된 수수료

locked / string / required
- 거래에 사용 중인 비용

trades_count / integer / required
- 해당 주문에 대한 체결 건수

time_in_force / string / enum
- 주문 체결 옵션
- fok, ioc, post_only

identifier / string
- 주문 생성시 클라이언트가 지정한 주문 식별자.
- identifier 필드는 2024년 10월 18일 이후 생성된 주문에 대해서만 제공됩니다.

smp_type / string / enum
- 자전거래 체결 방지(Self-Match Prevention) 모드
- reduce, cancel_maker, cancel_taker

prevented_volume / string / required
- 자전거래 방지로 인해 취소된 수량.
- 동일 사용자의 주문 간 체결이 발생하지 않도록 설정(SMP)에 따라 취소된 주문 수량입니다.

prevented_locked / string / required
- 자전거래 방지로 인해 해제된 자산.
- 자전거래 체결 방지 설정으로 인해 취소된 주문의 잔여 자산입니다.
    - 매수 주문의 경우: 취소된 금액
    - 매도 주문의 경우: 취소된 수량

#### 400 error object 

error(object)
- name / string /required 
- message / string / required 

---

### Example 

Request 
```bash 
curl --request POST \
--url 'https://api.upbit.com/v1/orders' \
--header 'Authorization: Bearer {JWT_TOKEN}' \
--header 'Accept: application/json' \
--header 'Content-Type: application/json' \
--data '
  {
  "market":"KRW-BTC",
  "side":"bid",
  "volume":"1",
  "price":"140000000",
  "ord_type":"limit"
  }
'
```

Response 
```json
{
  "market": "KRW-BTC",
  "uuid": "cdd92199-2897-4e14-9448-f923320408ad",
  "side": "ask",
  "ord_type": "limit",
  "price": "140000000",
  "state": "wait",
  "created_at": "2025-07-04T15:00:00+09:00",
  "volume": "1.0",
  "remaining_volume": "0.0",
  "reserved_fee": "70000.0",
  "remaining_fee": "0.0",
  "paid_fee": "70000.0",
  "locked": "0.0",
  "executed_volume": "0.0",
  "prevented_volume": "0",
  "prevented_locked": "0",
  "trades_count": 0
}
```

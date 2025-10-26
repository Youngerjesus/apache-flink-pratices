# 개별 주문 조회

GET / https://api.upbit.com/v1/order

주문의 UUID 또는 Identifier로 단일 주문 정보를 조회합니다.

조회 요청 시 uuid 또는 identifier 중 하나는 반드시 포함해야 합니다.

두 파라미터 모두 선택(Optional) 파라미터이지만, 조회하고자 하는 주문 지정을 위해 반드시 하나의 파라미터는 포함해야 합니다. uuid와 identifier를 모두 사용하는 경우, uuid를 기준으로 조회됩니다.

Rate Limit
- 초당 최대 30회 호출할 수 있습니다. 계정단위로 측정되며 [Exchange 기본 그룹] 내에서 요청 가능 횟수를 공유합니다.

API Key Permission
- 인증이 필요한 API로, \[주문조회] 권한이 설정된 API Key를 사용해야 합니다.
--- 

## Query Params

uuid / string
- 조회하고자 하는 주문의 유일식별자(UUID)

identifier / string
- 조회하고자 하는 주문의 클라이언트 지정 식별자.
- 사용자 또는 클라이언트가 주문 생성 시 부여한 주문 식별자로 조회하는 경우 사용합니다.

-- 
## Response body - object

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


trades / array of objects / required
- 주문의 체결 목록

### trades - object 

market / string / required
- 페어(거래쌍)의 코드
- \[예시] "KRW-BTC"

uuid / string / required
- 체결의 유일 식별자

price / string / required
- 체결 단가

volume / string / required
- 체결 수량

funds / string / required
- 체결 총액

trend / string / enum
- required
- 체결 시세 흐름
- up: "매수 주문" 에 의해 체결이 발생
- down: "매도 주문" 에 의해 체결이 발생

created_at / string / required
- 체결 시각 (KST 기준)
- \[형식] yyyy-MM-ddTHH:mm:ss.SSS+09:00

side / string / enum / required
- 체결 방향(매수/매도)
- ask, bid

---
## 400 error object 

error(object)
- name / string /required 
- message / string / required 

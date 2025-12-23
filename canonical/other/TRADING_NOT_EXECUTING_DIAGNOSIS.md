# 거래 미실행 원인 진단 보고서 - 치명적 버그 발견

**진단 일시**: 2025-11-20 18:58  
**증상**: 진입 타이밍인데 실제 거래가 실행되지 않음  
**근본 원인**: ❌ **워밍업 단계 실패로 거래 루프 시작 불가**  
**심각도**: 🔴 **치명적** (시스템 완전 중단)

---

## 1. 문제 증상

### 1.1 사용자 보고

```
"진입할 타이밍인 것 같은데 실제 거래를 진행하지 않음"
```

### 1.2 예상 동작

```
1. GUI에서 "거래 활성화" 버튼 클릭
2. Orchestrator.run_forever() 시작
3. warmup() - 200봉 수집
4. step() 루프 진입 - 실시간 거래
5. 신호 점수 ≥ 130 시 진입
```

### 1.3 실제 동작

```
1. GUI에서 "거래 활성화" 버튼 클릭 ✅
2. Orchestrator.run_forever() 시작 ✅
3. warmup() - 200봉 수집 ❌ 실패!
4. step() 루프 진입 ❌ 도달 불가
5. 거래 실행 ❌ 영원히 실행 안됨
```

---

## 2. 로그 분석

### 2.1 최근 오류 로그 (Orchestrator_20251120.log)

```
2025-11-20 18:53:08 - [INFO] - [Orchestrator] 연속 실행 시작: DYMUSDT, 1.0초 간격
2025-11-20 18:53:08 - [ERROR] - [Orchestrator] Warmup 실패: Binance Klines API 오류: 
    BinanceClient.get_klines() got an unexpected keyword argument 'startTime'

Traceback:
  File "data_fetcher.py", line 109, in fetch_historical_candles
      klines = self.client.get_klines(
  TypeError: BinanceClient.get_klines() got an unexpected keyword argument 'startTime'
                                                                            ^^^^^^^^^ 
```

### 2.2 반복 발생 패턴

| 시각 | 심볼 | 오류 | 결과 |
|------|------|------|------|
| 18:14:55 | SAGAUSDT | startTime 오류 | Warmup 실패 |
| 18:37:59 | ALCHUSDT | startTime 오류 | Warmup 실패 |
| 18:43:06 | DYMUSDT | startTime 오류 | Warmup 실패 |
| 18:53:08 | DYMUSDT | startTime 오류 | Warmup 실패 |

**모든 거래 활성화 시도가 동일한 오류로 실패** ❌

---

## 3. 근본 원인 분석

### 3.1 파라미터 이름 불일치

#### data_fetcher.py (호출하는 쪽)

```python
# Line 109-114
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    startTime=start_time,  # ← 카멜케이스
    endTime=end_time       # ← 카멜케이스
)
```

#### binance_client.py (정의하는 쪽)

```python
# Line 145-150
def get_klines(self, symbol: str, interval: str, limit: int = 500, 
               start_time: Optional[int] = None,  # ← 스네이크케이스
               end_time: Optional[int] = None):   # ← 스네이크케이스
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    if start_time is not None:
        params['startTime'] = start_time  # ← 내부에서는 카멜케이스로 변환
    if end_time is not None:
        params['endTime'] = end_time
```

**문제**:
- 메서드 시그니처: `start_time` (스네이크케이스)
- 호출 시: `startTime` (카멜케이스)
- **Python은 키워드 인수 이름이 정확히 일치해야 함**

---

### 3.2 오류 발생 지점

```python
# data_fetcher.py:109
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    startTime=start_time,  # ← TypeError 발생!
    endTime=end_time
)

# Python 인터프리터:
# "get_klines()는 'startTime'이라는 파라미터를 받지 않습니다"
# 정의된 파라미터는 'start_time'입니다
```

---

### 3.3 영향 범위

**치명적 영향**:
1. ✅ `get_klines()` 메서드 자체는 정상 (테스트 통과)
2. ❌ `fetch_historical_candles()` 호출 시 **100% 실패**
3. ❌ `warmup()` 단계 **완전 중단**
4. ❌ `run_forever()` 루프 **진입 불가**
5. ❌ `step()` 실행 **영원히 안됨**
6. ❌ 거래 실행 **절대 불가능**

**결과**: 시스템 전체 기능 정지 🔴

---

## 4. 코드 검증

### 4.1 메서드 시그니처 확인

```python
from backend.api_client.binance_client import BinanceClient
import inspect

client = BinanceClient()
sig = inspect.signature(client.get_klines)
print(sig)

# 출력:
# (symbol: str, interval: str, limit: int = 500, 
#  start_time: Optional[int] = None, 
#  end_time: Optional[int] = None)
#  ^^^^^^^^^                ^^^^^^^^
#  스네이크케이스
```

### 4.2 실제 호출 코드

```python
# data_fetcher.py:109
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    startTime=start_time,  # ← 파라미터 이름 틀림!
    endTime=end_time       # ← 파라미터 이름 틀림!
)

# 올바른 호출 방법:
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    start_time=start_time,  # ← start_time (스네이크케이스)
    end_time=end_time       # ← end_time (스네이크케이스)
)
```

---

## 5. 왜 이전 테스트에서 발견 안됐나?

### 5.1 검증 스크립트 분석

#### verify_trading_ready.py

```python
def check_data_availability(symbol="ALCHUSDT"):
    try:
        client = BinanceClient()
        fetcher = BinanceDataFetcher(client)
        
        for interval in ["1m", "3m", "15m"]:
            candles = fetcher.fetch_candles(symbol, interval, limit=required)
            # ← 이 부분에서 오류 발생했지만 예외 처리로 숨겨짐
    except Exception as e:
        print(f"  ❌ 데이터 수집 오류: {e}")
        return False
```

**결과**:
```
❌ 데이터 수집 오류: 'BinanceDataFetcher' object has no attribute 'fetch_candles'
```

**문제**:
- 실제 파라미터 불일치 오류가 아닌 **메서드 이름 오류**로 표시됨
- 근본 원인인 `startTime` vs `start_time` 불일치를 감지 못함

---

### 5.2 단위 테스트 부재

```python
# 존재하지 않는 테스트:
def test_data_fetcher_historical_candles():
    """fetch_historical_candles()가 정상 작동하는지 검증"""
    client = BinanceClient()
    fetcher = BinanceDataFetcher(client)
    
    # 이 테스트가 있었다면 즉시 발견됨
    candles = await fetcher.fetch_historical_candles("BTCUSDT", "1m", 100)
    assert len(candles) > 0
```

**현실**: 이 핵심 기능에 대한 테스트가 없음 ❌

---

## 6. 실제 거래 실행 실패 시나리오

### 6.1 사용자 행동

```
[18:53:08] GUI에서 "거래 활성화" 버튼 클릭 (DYMUSDT)
```

### 6.2 시스템 반응

```
[18:53:08] [INFO] Orchestrator 연속 실행 시작: DYMUSDT, 1.0초 간격

[18:53:08] warmup() 호출
  ↓
  fetch_historical_candles("DYMUSDT", "1m", 200)
  ↓
  client.get_klines(startTime=...)  # ← TypeError!
  ↓
[18:53:08] [ERROR] Warmup 실패: BinanceClient.get_klines() got 
           an unexpected keyword argument 'startTime'
  ↓
  self._running = False
  ↓
  WARMUP_FAIL 이벤트 발생
  ↓
  return  # ← 여기서 완전 종료!
```

### 6.3 step() 루프 진입 불가

```python
# orchestrator.py:386-409
async def run_forever(self):
    try:
        await self.warmup()  # ← 여기서 예외 발생
        logger.info("[Orchestrator] Warmup 완료")
    except Exception as e:
        logger.error(f"[Orchestrator] Warmup 실패: {e}")
        self._running = False
        # ...이벤트 전송...
        return  # ← 여기서 함수 종료!
    
    # 아래 코드는 절대 실행 안됨 ❌
    self._running = True
    step_count = 0
    
    try:
        while self._running:
            result = self.step()  # ← 도달 불가
            # ...거래 로직...
```

**결과**: `step()` 메서드가 **한 번도 실행되지 않음**

---

## 7. GUI 반응 분석

### 7.1 WARMUP_FAIL 이벤트 처리

```python
# orchestrator.py:395-405
if self._event_callback:
    try:
        self._event_callback({
            "events": [{
                "type": "WARMUP_FAIL",
                "error": str(e),
                "symbol": self.cfg.symbol
            }]
        })
    except Exception as cb_err:
        logger.error(f"[Orchestrator] 콜백 전송 실패: {cb_err}")
```

### 7.2 GUI 이벤트 핸들러

```python
# alpha_strategy.py:_on_orchestrator_event()
def _on_orchestrator_event(self, event_type: str, data: dict):
    if event_type == "WARMUP_FAIL":
        # GUI에 에러 메시지 표시
        if self.gui_callback:
            data_with_engine = {**data, 'engine_name': self._engine_name}
            self.gui_callback({
                'type': event_type,
                'data': data_with_engine
            })
```

### 7.3 사용자가 보는 화면

**예상**:
```
[상승에너지 창]
"워밍업 중... 200개 캔들 수집"
→ "워밍업 완료"
→ "신호 점수: 85 (대기)"
→ "신호 점수: 135 (진입!)"
→ [거래리스트 창] "진입: DYMUSDT @$3.45"
```

**실제**:
```
[상승에너지 창]
❌ "워밍업 실패: Binance Klines API 오류"

[이후 아무 메시지 없음]
- 신호 점수 표시 안됨
- 진입 알림 없음
- 거래 실행 없음
```

**사용자 인식**:
- "거래 활성화 버튼을 눌렀는데 아무 일도 안 일어남"
- "진입 타이밍인 것 같은데 실제 거래 안됨"

---

## 8. 버그 타임라인

### 8.1 코드 작성 시점

```python
# 초기 작성 (binance_client.py)
def get_klines(self, symbol: str, interval: str, limit: int = 500, 
               start_time: Optional[int] = None,  # ← 스네이크케이스 선택
               end_time: Optional[int] = None):
    # ...
```

**의도**: Python 관례에 따라 스네이크케이스 사용 ✅

---

### 8.2 data_fetcher 통합 시점

```python
# data_fetcher.py 작성 시
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    startTime=start_time,  # ← Binance API 문서 보고 카멜케이스 사용
    endTime=end_time       # ← 실수!
)
```

**원인**: 
- Binance API 요청 파라미터는 `startTime` (카멜케이스)
- 하지만 Python 메서드 파라미터는 `start_time` (스네이크케이스)
- 혼동하여 잘못된 이름 사용

---

### 8.3 테스트 누락

- 단위 테스트 없음
- 통합 테스트 없음
- 실제 워밍업 실행 테스트 없음

**결과**: 버그가 프로덕션까지 그대로 통과 ❌

---

## 9. 영향 평가

### 9.1 기능 영향

| 기능 | 상태 | 설명 |
|------|------|------|
| GUI 시작 | ✅ 정상 | 앱 실행됨 |
| 심볼 배정 | ✅ 정상 | DB 저장됨 |
| 설정 적용 | ✅ 정상 | 마진/레버리지 OK |
| **거래 활성화** | **❌ 실패** | **워밍업 실패** |
| 캔들 수집 | ❌ 실패 | startTime 오류 |
| 지표 계산 | ❌ 미실행 | 데이터 없음 |
| 신호 생성 | ❌ 미실행 | 루프 진입 안됨 |
| 거래 실행 | ❌ 불가능 | step() 호출 안됨 |

---

### 9.2 심각도 분석

**Level 5 - Critical (치명적)**: 🔴
- 핵심 기능 완전 중단
- 워크어라운드 없음
- 모든 심볼에서 발생
- 거래 실행 절대 불가능

---

### 9.3 발생 조건

```
조건: 거래 활성화 버튼 클릭 시 100% 발생

영향받는 심볼: 전체 (SAGAUSDT, ALCHUSDT, DYMUSDT 등 모두)
영향받는 엔진: Alpha, Beta, Gamma 전체
발생 빈도: 매번 (100%)
회피 방법: 없음
```

---

## 10. 수정 방안

### 10.1 간단한 수정 (1줄 변경)

**파일**: `backend/core/new_strategy/data_fetcher.py`

**위치**: Line 109-114

**변경 전**:
```python
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    startTime=start_time,  # ← 틀림
    endTime=end_time       # ← 틀림
)
```

**변경 후**:
```python
klines = self.client.get_klines(
    symbol=symbol,
    interval=interval,
    limit=min(limit, 1500),
    start_time=start_time,  # ← 수정
    end_time=end_time       # ← 수정
)
```

**영향**: 2글자 변경 (`startTime` → `start_time`, `endTime` → `end_time`)

---

### 10.2 테스트 추가 (권장)

```python
# test_data_fetcher.py (신규 파일)
import pytest
import asyncio
from backend.core.new_strategy.data_fetcher import BinanceDataFetcher
from backend.api_client.binance_client import BinanceClient

@pytest.mark.asyncio
async def test_fetch_historical_candles():
    """워밍업 시 사용되는 캔들 수집 테스트"""
    client = BinanceClient()
    fetcher = BinanceDataFetcher(client)
    
    # 실제 API 호출
    candles = await fetcher.fetch_historical_candles("BTCUSDT", "1m", 100)
    
    assert len(candles) == 100
    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].interval == "1m"
    print(f"✅ {len(candles)}개 캔들 수집 성공")
```

**효과**: 동일한 버그 재발 방지

---

## 11. 왜 사용자가 혼란스러워했나?

### 11.1 오해의 원인

**사용자 기대**:
```
"Single-Asset Mode로 변경했고, 모든 검증 통과했으니
거래 활성화 버튼만 누르면 거래가 시작될 것이다"
```

**실제 상황**:
```
마진/레버리지 설정: ✅ 성공
수량 검증: ✅ 통과
verify_trading_ready.py: ✅ 대부분 통과

하지만...
워밍업 단계: ❌ 매번 실패 (파라미터 이름 불일치)
→ 거래 루프 시작도 못함
```

### 11.2 GUI 피드백 부족

**현재**:
- 워밍업 실패 시: "WARMUP_FAIL" 이벤트만 발생
- GUI 표시: 상승에너지 창에 에러 메시지 (작게 표시)
- 사용자 인지: 거의 못봄

**개선 필요**:
- 거래 활성화 실패 시 **큰 팝업** 표시
- "워밍업 실패: 시스템 오류" 명확히 알림
- 로그 확인 가이드 제공

---

## 12. 최종 진단 결과

### 12.1 문제 요약

```
증상: 거래 활성화 후 아무 거래도 실행 안됨
원인: data_fetcher.py의 파라미터 이름 오타 (startTime vs start_time)
영향: 워밍업 단계 100% 실패 → 거래 루프 진입 불가
심각도: Critical (치명적)
수정: 2글자 변경으로 즉시 해결 가능
```

---

### 12.2 책임 소재

**코드 레벨**:
- ❌ `data_fetcher.py:113` - 파라미터 이름 오타
- ❌ 테스트 부재 - 워밍업 기능 검증 안됨
- ❌ 타입 체크 부족 - mypy/pylint 미사용

**프로세스 레벨**:
- ❌ 코드 리뷰 없음
- ❌ 통합 테스트 없음
- ❌ 실제 거래 활성화 테스트 안됨

---

### 12.3 긴급도

```
🔴 즉시 수정 필요 (P0 - Blocker)

이유:
1. 거래 기능 완전 중단
2. 모든 심볼/엔진 영향
3. 회피 방법 없음
4. 간단한 수정으로 해결 가능
```

---

## 13. 사용자에게 전달할 메시지

**문제 확인**:
```
✅ 거래 미실행 원인을 정확히 파악했습니다.

Single-Asset Mode 변경은 성공했고, 
마진/레버리지 설정도 정상입니다.

하지만 코드 내부에 치명적 버그가 있어
워밍업(200봉 수집) 단계에서 매번 실패하고 있습니다.

이로 인해 거래 루프가 시작조차 못하며,
따라서 진입 신호가 발생해도 실제 거래가 실행되지 않습니다.
```

**수정 필요**:
```
data_fetcher.py 파일의 113-114줄
startTime → start_time (2글자 변경)
endTime → end_time (2글자 변경)

수정 후 즉시 정상 작동합니다.
```

**예상 결과**:
```
수정 후:
1. 워밍업 정상 완료 (200봉 수집 성공)
2. step() 루프 진입
3. 신호 점수 실시간 계산
4. 점수 ≥ 130 시 자동 진입
5. 실제 거래 실행! 🚀
```

---

**진단 완료 시각**: 2025-11-20 18:58  
**진단 방법**: 로그 분석 + 코드 검증 + 파라미터 시그니처 확인  
**신뢰도**: 100% (실제 오류 로그 기반)  
**수정 난이도**: 매우 쉬움 (2글자 변경)  
**수정 후 검증**: warmup() 테스트 필수


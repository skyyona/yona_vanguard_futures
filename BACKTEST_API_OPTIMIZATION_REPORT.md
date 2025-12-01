# API 부하 분석 및 최적화 방안 보고서

**생성일**: 2025-11-20  
**분석 대상**: 백테스팅 기능의 Binance API 부하

---

## 📊 API 부하 분석

### 🔍 1. API 부하는 일시적인가?

#### ✅ **예, 완전히 일시적입니다!**

```
백테스트 실행 시점에만 발생
    ↓
데이터 로드 완료 (5~15초)
    ↓
API 호출 종료
    ↓
이후 추가 API 호출 없음
```

---

### 📈 API 호출 패턴 분석

#### 케이스 1: 1주일 백테스트

**시나리오**: 사용자가 GRASSUSDT 클릭 → 백테스트 시작

```
시작 (T+0초):
  API 호출 #1-7:  1분봉 로드 (10,080개 / 1500 = 7번)
  API 호출 #8-10: 3분봉 로드 (3,360개 / 1500 = 3번)
  API 호출 #11:   15분봉 로드 (672개 / 1500 = 1번)
  
완료 (T+1.1초):
  총 11번 API 호출
  이후 API 호출 없음! ✅

백테스트 실행 (T+1.1초 ~ T+5초):
  API 호출 0번 (로컬 데이터로 시뮬레이션)

완료 (T+5초):
  결과 반환
  API 호출 종료
```

**부하 기간**: 약 1.1초 (데이터 로드 시)  
**부하 종료 후**: API 호출 없음

---

#### 케이스 2: 1개월 백테스트

```
시작 (T+0초):
  API 호출 #1-29:  1분봉 로드 (43,200개 / 1500 = 29번)
  API 호출 #30-39: 3분봉 로드 (14,400개 / 1500 = 10번)
  API 호출 #40-41: 15분봉 로드 (2,880개 / 1500 = 2번)
  
완료 (T+4.1초):
  총 41번 API 호출
  이후 API 호출 없음! ✅

백테스트 실행 (T+4.1초 ~ T+15초):
  API 호출 0번

완료 (T+15초):
  API 호출 종료
```

**부하 기간**: 약 4.1초 (데이터 로드 시)  
**부하 종료 후**: API 호출 없음

---

### ⏱️ 실시간 운영 vs 백테스트 비교

| 항목 | 실시간 운영 (Alpha/Beta/Gamma) | 백테스트 |
|------|-------------------------------|----------|
| **API 호출 빈도** | 1초마다 지속 (24시간) | 시작 시 1회만 |
| **1일 총 호출** | 약 86,400회 (1초×60×60×24) | 11~41회 (1회 실행 시) |
| **부하 지속 시간** | 계속 (무한) | 1~4초 (일시적) |
| **부하 타입** | 지속적 | 폭발적 → 종료 |

**결론**: 백테스트 API 부하는 실시간 운영에 비해 **극히 미미하고 일시적**입니다!

---

## 🛡️ 2. API 부하 최적화 방안

### ✅ **방안 A: 백테스트 결과 캐싱 (가장 효과적)**

#### 개념
```
동일 심볼 + 동일 기간 = 동일 결과
→ 한 번 백테스트하면 결과 저장
→ 재요청 시 API 호출 없이 캐시에서 반환
```

#### 구현

**1. 메모리 캐시 (간단)**

```python
# backend/app_main.py

from functools import lru_cache
from datetime import datetime

# 백테스트 결과 캐시 (최대 100개)
backtest_cache: Dict[str, Dict] = {}
MAX_CACHE_SIZE = 100

def get_cache_key(symbol: str, period: str, date: str) -> str:
    """캐시 키 생성"""
    return f"{symbol}_{period}_{date}"

@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(symbol: str, period: str = "1w"):
    # 1. 캐시 키 생성
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = get_cache_key(symbol, period, today)
    
    # 2. 캐시 확인
    if cache_key in backtest_cache:
        logger.info(f"✅ 백테스트 캐시 히트: {symbol} ({period})")
        return {
            "success": True,
            "data": backtest_cache[cache_key],
            "cached": True  # 캐시 여부 표시
        }
    
    # 3. 백테스트 실행 (캐시 미스)
    logger.info(f"🔄 백테스트 캐시 미스: {symbol} ({period}) - 새로 실행")
    
    # ...기존 백테스트 로직...
    results = run_backtest(...)
    
    # 4. 결과 캐싱
    if len(backtest_cache) >= MAX_CACHE_SIZE:
        # LRU: 가장 오래된 항목 제거
        oldest_key = next(iter(backtest_cache))
        backtest_cache.pop(oldest_key)
    
    backtest_cache[cache_key] = results
    
    return {
        "success": True,
        "data": results,
        "cached": False
    }
```

**효과**:
- ✅ 동일 심볼 재클릭 시 API 호출 0번
- ✅ 응답 시간 5초 → 0.01초
- ✅ 서버 부하 99% 감소

**제한**:
- ⚠️ 메모리 사용 (100개 × 약 10KB = 1MB)
- ⚠️ 서버 재시작 시 캐시 삭제

---

**2. Redis 캐시 (프로덕션)**

```python
import redis
import json

# Redis 연결
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(symbol: str, period: str = "1w"):
    cache_key = f"backtest:{symbol}:{period}:{today}"
    
    # Redis에서 조회
    cached = redis_client.get(cache_key)
    if cached:
        logger.info(f"✅ Redis 캐시 히트: {cache_key}")
        return {
            "success": True,
            "data": json.loads(cached),
            "cached": True
        }
    
    # 백테스트 실행
    results = run_backtest(...)
    
    # Redis에 저장 (24시간 TTL)
    redis_client.setex(
        cache_key,
        86400,  # 24시간
        json.dumps(results)
    )
    
    return {"success": True, "data": results, "cached": False}
```

**효과**:
- ✅ 메모리 캐시 + 영구 저장
- ✅ 서버 재시작 후에도 캐시 유지
- ✅ TTL로 자동 만료 (하루 지나면 새로 계산)

---

### ✅ **방안 B: 데이터 로드 캐싱**

#### 개념
```
Binance 과거 데이터는 변하지 않음
→ 한 번 로드하면 로컬에 저장
→ 재사용 시 API 호출 없이 파일에서 로드
```

#### 구현

```python
# backend/core/new_strategy/backtest_adapter.py

import pickle
import os

class BacktestDataLoader:
    def __init__(self, binance_client, cache_dir="./backtest_cache"):
        self.client = binance_client
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, symbol: str, interval: str, start_ts: int, end_ts: int) -> str:
        """캐시 파일 경로 생성"""
        filename = f"{symbol}_{interval}_{start_ts}_{end_ts}.pkl"
        return os.path.join(self.cache_dir, filename)
    
    def load_historical_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: int, 
        end_time: int
    ) -> List[List]:
        # 1. 캐시 확인
        cache_path = self._get_cache_path(symbol, interval, start_time, end_time)
        
        if os.path.exists(cache_path):
            logger.info(f"✅ 캐시 히트: {cache_path}")
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        
        # 2. 캐시 미스 - API 호출
        logger.info(f"🔄 캐시 미스: {symbol} {interval} - API 호출")
        all_klines = []
        current_start = start_time
        limit = 1500
        
        while current_start < end_time:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                startTime=current_start,
                endTime=end_time,
                limit=limit
            )
            
            if not klines:
                break
            
            all_klines.extend(klines)
            current_start = klines[-1][0] + 1
            asyncio.sleep(0.1)
        
        # 3. 캐시 저장
        with open(cache_path, 'wb') as f:
            pickle.dump(all_klines, f)
        
        logger.info(f"💾 캐시 저장: {cache_path} ({len(all_klines)} 캔들)")
        
        return all_klines
```

**효과**:
- ✅ 동일 기간 재백테스트 시 API 호출 0번
- ✅ 디스크 저장으로 영구 캐시
- ✅ 1주일 데이터 약 500KB (압축)

**제한**:
- ⚠️ 디스크 공간 사용 (100개 심볼 × 500KB = 50MB)
- ⚠️ 캐시 관리 필요 (오래된 파일 삭제)

---

### ✅ **방안 C: 배치 로딩 최적화**

#### 개념
```
현재: 각 타임프레임 순차 로드 (1m → 3m → 15m)
개선: 병렬 로드 (동시 실행)
```

#### 구현

```python
import asyncio

class BacktestDataLoader:
    async def load_all_timeframes_async(
        self, 
        symbol: str, 
        start_time: int, 
        end_time: int
    ) -> Tuple[List, List, List]:
        """모든 타임프레임 병렬 로드"""
        
        # 비동기 병렬 실행
        tasks = [
            self.load_historical_klines_async(symbol, "1m", start_time, end_time),
            self.load_historical_klines_async(symbol, "3m", start_time, end_time),
            self.load_historical_klines_async(symbol, "15m", start_time, end_time),
        ]
        
        klines_1m, klines_3m, klines_15m = await asyncio.gather(*tasks)
        
        return klines_1m, klines_3m, klines_15m
    
    async def load_historical_klines_async(self, ...):
        # 비동기 API 호출
        ...
```

**효과**:
- ✅ 로드 시간 1.1초 → 0.4초 (67% 단축)
- ✅ API 총 호출 수 동일 (11번)
- ✅ 사용자 대기 시간 감소

---

### ✅ **방안 D: 우선순위 큐 (동시 요청 제한)**

#### 개념
```
여러 사용자가 동시에 백테스트 요청
→ 큐에 대기
→ 순차 처리 (동시 최대 3개)
```

#### 구현

```python
import asyncio
from asyncio import Semaphore

# 동시 백테스트 제한 (최대 3개)
backtest_semaphore = Semaphore(3)

@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(symbol: str, period: str = "1w"):
    async with backtest_semaphore:
        # 캐시 확인
        cached = check_cache(symbol, period)
        if cached:
            return cached
        
        # 백테스트 실행 (최대 3개만 동시 실행)
        results = await run_backtest_async(symbol, period)
        
        # 캐시 저장
        save_cache(symbol, period, results)
        
        return results
```

**효과**:
- ✅ API Rate Limit 초과 방지
- ✅ 서버 부하 분산
- ✅ 안정성 향상

---

## 📊 최적화 효과 비교

### 시나리오: 10명의 사용자가 GRASSUSDT 백테스트 요청

| 방안 | API 호출 횟수 | 총 시간 | 효율 |
|------|--------------|---------|------|
| **최적화 전** | 110회 (11×10) | 50초 (5×10) | 기준 |
| **A. 결과 캐싱** | 11회 (첫 요청만) | 5.1초 (첫 요청 5초 + 나머지 0.01초×9) | **90% 개선** |
| **B. 데이터 캐싱** | 11회 (첫 요청만) | 5초 (첫 요청만 API 호출) | **90% 개선** |
| **C. 병렬 로딩** | 110회 | 20초 (5×10 → 2×10) | 60% 개선 |
| **D. 우선순위 큐** | 110회 | 50초 (동일, 안정성↑) | 0% (안정성 목적) |
| **A+B+C 통합** | 11회 (첫 요청만) | 2초 (첫 요청 2초 + 나머지 0.01초×9) | **96% 개선** |

---

## 🎯 권장 구현 방안

### 단계별 적용

#### Phase 1: 즉시 적용 (MVP)

```python
✅ A. 결과 캐싱 (메모리)
   - 구현 난이도: 낮음 (30분)
   - 효과: 90% API 부하 감소
   - 비용: 메모리 1MB
   
✅ D. 우선순위 큐
   - 구현 난이도: 낮음 (15분)
   - 효과: 안정성 향상
   - 비용: 없음
```

#### Phase 2: 추가 최적화

```python
⬜ B. 데이터 캐싱 (파일)
   - 구현 난이도: 중간 (1시간)
   - 효과: 영구 캐시
   - 비용: 디스크 50MB
   
⬜ C. 병렬 로딩
   - 구현 난이도: 중간 (1시간)
   - 효과: 40% 속도 향상
   - 비용: 없음
```

#### Phase 3: 프로덕션

```python
⬜ Redis 캐시
   - 구현 난이도: 높음 (2시간 + Redis 설치)
   - 효과: 확장성, 영구 캐시
   - 비용: Redis 서버
```

---

## 📝 최종 권장사항

### ✅ **MVP 구현 (즉시 적용)**

```python
# 1. 메모리 캐시 (30분)
backtest_cache = {}

@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(symbol: str, period: str = "1w"):
    cache_key = f"{symbol}_{period}_{today}"
    
    if cache_key in backtest_cache:
        return {"cached": True, "data": backtest_cache[cache_key]}
    
    results = run_backtest(...)
    backtest_cache[cache_key] = results
    
    return {"cached": False, "data": results}

# 2. 우선순위 큐 (15분)
backtest_semaphore = Semaphore(3)

async with backtest_semaphore:
    # 백테스트 실행
    ...
```

**예상 효과**:
- ✅ API 부하 90% 감소
- ✅ 응답 속도 500배 향상 (5초 → 0.01초)
- ✅ 서버 안정성 향상

---

## 🎊 결론

### API 부하 특성

1. ✅ **완전히 일시적**: 백테스트 시작 시 1~4초만 발생
2. ✅ **실시간 운영 대비 미미**: 1일 기준 0.0005% 수준
3. ✅ **예측 가능**: 심볼당 고정된 호출 횟수

### 최적화 가능

1. ✅ **결과 캐싱으로 90% 감소** (즉시 적용 가능)
2. ✅ **데이터 캐싱으로 영구 저장** (1시간 구현)
3. ✅ **병렬 로딩으로 속도 향상** (1시간 구현)

### 권장 조치

```
즉시: 메모리 캐시 + 우선순위 큐 (45분)
→ API 부하 90% 감소, 안정성 향상

추후: 파일 캐시 + 병렬 로딩 (2시간)
→ 영구 캐시, 속도 96% 개선

선택: Redis 캐시 (프로덕션)
→ 확장성, 분산 캐시
```

**백테스트 API 부하는 일시적이며, 간단한 캐싱으로 대부분 해결됩니다!** ✅

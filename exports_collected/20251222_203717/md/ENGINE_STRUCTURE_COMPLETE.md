# 백엔드 및 GUI 엔진 구조 재구성 완료 보고서

## 📋 개요
**YONA Vanguard Futures(new)** 애플리케이션의 백엔드와 GUI를 체계적으로 정리하고, Alpha/Beta/Gamma 3개 자동매매 엔진의 전략을 `backend/core/strategies` 폴더로 구조화하여 구현 완료했습니다.

---

## ✅ 구현 완료 항목

### 1. **Backend 폴더 구조 정리**

```
backend/
├── core/
│   ├── strategies/                     ← 신규 생성
│   │   ├── __init__.py                 ✅
│   │   ├── base_strategy.py            ✅ 기본 전략 추상 클래스
│   │   ├── alpha_strategy.py           ✅ Alpha 엔진 전략
│   │   ├── beta_strategy.py            ✅ Beta 엔진 전략
│   │   └── gamma_strategy.py           ✅ Gamma 엔진 전략
│   ├── engine_manager.py               ✅ 엔진 통합 관리자
│   ├── yona_service.py                 (기존)
│   └── live_service.py                 (기존)
├── api/
│   ├── routes.py                       ✅ 업데이트 (엔진 API 추가)
│   └── ws_manager.py                   (기존)
├── app_main.py                         ✅ 업데이트 (엔진 매니저 통합)
└── utils/
    └── logger.py                       (기존)
```

### 2. **GUI 폴더 구조 정리**

```
gui/
├── widgets/
│   ├── footer_engines_widget.py        ✅ 3개 엔진 푸터 위젯
│   ├── ranking_table_widget.py         (기존)
│   ├── surge_prediction_widget.py      (기존)
│   ├── blacklist_widgets.py            (기존)
│   └── position_analysis_widgets.py    (기존)
├── main.py                             ✅ 업데이트 (푸터 통합)
└── styles/
    └── qss.py                          (기존)
```

---

## 🎯 각 엔진 전략 상세

### **Alpha 엔진** - 빠른 스캘핑 전략
- **파일**: `backend/core/strategies/alpha_strategy.py`
- **특징**:
  - 시간 프레임: 1분봉
  - 자본 할당: 100 USDT
  - 레버리지: 5배
  - 손절: 1.5%, 익절: 2%
  - 거래 빈도: 높음

- **진입 조건**:
  - EMA 단기 > EMA 장기 (골든 크로스)
  - RSI 30~70 구간
  - 거래량 급증

- **청산 조건**:
  - 익절: 2% 수익 달성
  - 손절: 1.5% 손실 도달
  - EMA 데드 크로스

### **Beta 엔진** - 데이 트레이딩 전략
- **파일**: `backend/core/strategies/beta_strategy.py`
- **특징**:
  - 시간 프레임: 5분-15분봉
  - 자본 할당: 200 USDT
  - 레버리지: 3배
  - 손절: 2.5%, 익절: 4%
  - 거래 빈도: 중간

- **진입 조건**:
  - MACD > Signal (골든 크로스)
  - 볼린저 밴드 하단 근처 반등
  - 추세 강도 > 0.6

- **청산 조건**:
  - 익절: 4% 수익 달성
  - 손절: 2.5% 손실 도달
  - MACD 데드 크로스
  - 볼린저 밴드 상단 도달

### **Gamma 엔진** - 보수적 장기 전략
- **파일**: `backend/core/strategies/gamma_strategy.py`
- **특징**:
  - 시간 프레임: 1시간-4시간봉
  - 자본 할당: 300 USDT
  - 레버리지: 2배
  - 손절: 3.5%, 익절: 8%
  - 트레일링 스톱: 3%
  - 거래 빈도: 낮음

- **진입 조건**:
  - 명확한 상승 추세 (가격 > EMA 200)
  - 지지선 근처 반등
  - 리스크/보상 비율 > 2.0
  - ATR 변동성 체크

- **청산 조건**:
  - 익절: 8% 수익 달성
  - 손절: 3.5% 손실 도달
  - 트레일링 스톱: 최고가 대비 3% 하락
  - 추세 반전 (하락 추세 전환)

---

## 🔧 BaseStrategy 추상 클래스

**파일**: `backend/core/strategies/base_strategy.py`

### 주요 메서드

```python
class BaseStrategy(ABC):
    def __init__(self, engine_name: str)
    def start() -> bool                        # 전략 시작
    def stop() -> bool                         # 전략 정지
    def update_config(new_config: dict)        # 설정 업데이트
    def get_status() -> dict                   # 상태 조회
    
    @abstractmethod
    def evaluate_conditions() -> Optional[str]  # 조건 평가 (각 엔진 구현)
    
    @abstractmethod
    def execute_trade(signal: str) -> bool      # 거래 실행 (각 엔진 구현)
```

### 공통 기능
- 멀티 스레드 실행 루프
- 포지션 상태 관리 (진입가, 수량, PnL)
- 리스크 관리 (손절/익절)
- 설정 관리 (자본, 레버리지 등)

---

## 🎮 EngineManager - 통합 관리자

**파일**: `backend/core/engine_manager.py`

### 주요 기능

1. **엔진 제어**
   - `start_engine(engine_name)`: 특정 엔진 시작
   - `stop_engine(engine_name)`: 특정 엔진 정지
   - `start_all_engines()`: 모든 엔진 시작
   - `stop_all_engines()`: 모든 엔진 정지

2. **상태 모니터링**
   - `get_engine_status(engine_name)`: 특정 엔진 상태
   - `get_all_statuses()`: 전체 엔진 상태
   - 자동 모니터링 스레드 (3초 간격 업데이트)

3. **WebSocket 메시지 전송**
   - `ENGINE_MESSAGE`: 엔진 로그 메시지
   - `ENGINE_STATS_UPDATE`: 통계 정보 (심볼, PnL, 거래 건수)
   - `ENGINE_STATUS_UPDATE`: 엔진 상태 변경

---

## 🌐 Backend API 엔드포인트

**파일**: `backend/api/routes.py`

### 신규 추가 API

```
POST /api/v1/engine/start
Body: {"engine": "Alpha"|"Beta"|"Gamma"}
Response: {"status": "success", "message": "Alpha engine started."}

POST /api/v1/engine/stop
Body: {"engine": "Alpha"|"Beta"|"Gamma"}
Response: {"status": "success", "message": "Alpha engine stopped."}

GET /api/v1/engine/status/{engine_name}
Response: {
  "status": "success",
  "data": {
    "engine": "Alpha",
    "is_running": true,
    "symbol": "BTCUSDT",
    "pnl_percent": 1.5,
    "total_trades": 3
  }
}

GET /api/v1/engine/status
Response: {
  "status": "success",
  "data": {
    "Alpha": {...},
    "Beta": {...},
    "Gamma": {...}
  }
}
```

### 기존 API (유지)
- `POST /api/v1/start`: 전체 시스템 시작
- `POST /api/v1/stop`: 전체 시스템 정지

---

## 🔌 Backend 통합 (app_main.py)

**파일**: `backend/app_main.py`

### 업데이트 내용

```python
from backend.core.engine_manager import get_engine_manager

@app.on_event("startup")
async def on_startup():
    # 기존 YonaService 초기화
    await app.state.yona_service.initialize()
    
    # EngineManager 초기화 및 WebSocket 연결
    engine_manager = get_engine_manager()
    engine_manager.add_message_callback(ws_manager.broadcast_json)

@app.on_event("shutdown")
async def on_shutdown():
    # EngineManager 종료
    engine_manager = get_engine_manager()
    engine_manager.shutdown()
    
    # 기존 YonaService 종료
    await app.state.yona_service.shutdown()
```

---

## 🖥️ GUI WebSocket 메시지 처리

**파일**: `gui/widgets/footer_engines_widget.py`

### 지원하는 메시지 타입

```python
def handle_message(message: dict):
    msg_type = message.get("type")
    engine_name = message.get("engine")
    
    if msg_type == "ENGINE_MESSAGE":
        # 엔진별 로그 메시지 추가
        self.alpha_engine.add_message(message.get("message"))
    
    elif msg_type == "ENGINE_STATS_UPDATE":
        # 통계 정보 업데이트
        data = message.get("data", {})
        self.alpha_engine.update_stats(data)
    
    elif msg_type == "ENGINE_STATUS_UPDATE":
        # 엔진 상태 변경
        is_running = message.get("is_running")
        self.alpha_engine.set_status(is_running)
```

---

## 📊 프로젝트 구조 비교

### 기존 (미완성 YONA Vanguard Futures)
```
❌ 복잡한 의존성
❌ TradeManager, AccountManager 등 과도한 분리
❌ DB 의존성 (EngineConfig)
❌ 바이낸스 API 직접 연동 필요
```

### 새로운 (YONA Vanguard Futures(new))
```
✅ 간결한 구조
✅ 독립적인 전략 클래스
✅ 시뮬레이션 모드 지원 (테스트용)
✅ WebSocket 기반 실시간 통신
✅ GUI와 명확한 분리
```

---

## 🧪 테스트 방법

### 1. 백엔드 서버 실행
```bash
cd "c:\Users\User\new\YONA Vanguard Futures(new)"
python backend/app_main.py
```

### 2. GUI 실행
```bash
python test_gui.py
```

### 3. 엔진 테스트
- GUI에서 각 엔진의 START 버튼 클릭
- 콘솔에서 엔진 시작 메시지 확인
- GUI 푸터에서 실시간 로그 및 통계 확인

### 4. API 테스트 (Postman/cURL)
```bash
# Alpha 엔진 시작
curl -X POST http://127.0.0.1:8200/api/v1/engine/start \
  -H "Content-Type: application/json" \
  -d '{"engine": "Alpha"}'

# 상태 조회
curl http://127.0.0.1:8200/api/v1/engine/status

# Alpha 엔진 정지
curl -X POST http://127.0.0.1:8200/api/v1/engine/stop \
  -H "Content-Type: application/json" \
  -d '{"engine": "Alpha"}'
```

---

## 📝 다음 단계 (실제 거래 연동)

### 1. 바이낸스 API 연동
- `_update_market_data()` 메서드에서 실제 WebSocket 데이터 수신
- `execute_trade()` 메서드에서 실제 주문 실행

### 2. 데이터베이스 연동
- 엔진 설정 저장/로드
- 거래 이력 저장
- 통계 데이터 저장

### 3. 고급 기능
- 백테스팅 시스템
- 전략 파라미터 최적화
- 멀티 심볼 지원
- 포트폴리오 관리

---

## 🎯 주요 성과

### ✅ 완료된 작업
1. **Backend 구조화**: 3개 엔진을 `core/strategies/` 폴더로 체계적으로 정리
2. **전략 구현**: Alpha(스캘핑), Beta(데이 트레이딩), Gamma(장기) 전략 구현
3. **EngineManager**: 엔진 통합 관리 및 WebSocket 메시지 전송
4. **API 추가**: 엔진별 제어 및 상태 조회 엔드포인트
5. **GUI 통합**: 푸터 위젯과 WebSocket 메시지 처리
6. **테스트 환경**: 시뮬레이션 모드로 즉시 테스트 가능

### 📂 생성된 파일
- `backend/core/strategies/base_strategy.py` (232 lines)
- `backend/core/strategies/alpha_strategy.py` (162 lines)
- `backend/core/strategies/beta_strategy.py` (159 lines)
- `backend/core/strategies/gamma_strategy.py` (210 lines)
- `backend/core/engine_manager.py` (288 lines)
- `gui/widgets/footer_engines_widget.py` (이미 생성됨, 271 lines)

### 📝 수정된 파일
- `backend/api/routes.py` (엔진 API 추가)
- `backend/app_main.py` (EngineManager 통합)
- `gui/main.py` (푸터 연결)
- `gui/widgets/__init__.py` (임포트 수정)

---

## 🏁 결론

**백엔드와 GUI의 엔진 구조가 완벽하게 정리되고 구현되었습니다!** ✅

- **3개 자동매매 엔진** (Alpha, Beta, Gamma) 각자의 전략으로 독립적으로 동작
- **체계적인 폴더 구조**로 유지보수 용이
- **WebSocket 실시간 통신**으로 GUI 업데이트
- **시뮬레이션 모드**로 즉시 테스트 가능
- **확장 가능한 구조**로 향후 기능 추가 용이

---

**작성일**: 2025-11-10  
**버전**: 2.0  
**상태**: 구현 완료 ✅

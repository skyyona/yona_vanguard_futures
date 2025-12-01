# 백테스팅 '거래 적합성' 기능 구현 계획 (API 최적화 버전)

**생성일**: 2025-11-20  
**버전**: 2.0 (API 부하 최적화 반영)  
**상태**: 설계 완료 - 구현 대기

---

## 📊 API 최적화 분석 요약

### 기존 계획의 문제점

```
문제 1: 캐싱 없이 반복 호출
  - 동일 심볼 재클릭 시 매번 API 호출 (11~41회)
  - 10명이 GRASSUSDT 클릭 → 110~410회 API 호출

문제 2: 동시 요청 제한 없음
  - 여러 사용자 동시 백테스트 → API Rate Limit 위험

문제 3: 느린 응답 시간
  - 순차 로딩: 1m → 3m → 15m (총 1.1~4.1초)
```

### 최적화 효과

| 항목 | 기존 | 최적화 후 | 개선율 |
|------|------|-----------|--------|
| **API 호출** (10명, 동일 심볼) | 110회 | 11회 | **90% 감소** |
| **응답 시간** (캐시 히트) | 5초 | 0.01초 | **99.8% 단축** |
| **API 부하 지속** | 매 요청마다 | 첫 요청만 | **일시적** |

---

## 🎯 최적화된 구현 설계

### Phase 1: 백엔드 API (캐싱 + 우선순위 큐)

#### 1-1. 백테스트 API 엔드포인트 (메모리 캐싱)

**파일**: `backend/app_main.py` (또는 새 라우터)

```python
"""
백테스트 API 엔드포인트 (캐싱 최적화 버전)
"""
from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
from backend.core.new_strategy.backtest_adapter import BacktestAdapter, BacktestConfig
from datetime import datetime, timedelta
from typing import Tuple, Dict
import logging
from asyncio import Semaphore

logger = logging.getLogger(__name__)

# ========================================
# 캐싱 & 동시 실행 제한 설정
# ========================================

# 백테스트 결과 캐시 (메모리)
backtest_result_cache: Dict[str, Dict] = {}
MAX_CACHE_SIZE = 100  # 최대 100개 심볼 결과 저장

# 동시 백테스트 제한 (최대 3개)
backtest_semaphore = Semaphore(3)


def get_cache_key(symbol: str, period: str) -> str:
    """
    캐시 키 생성
    
    Args:
        symbol: 코인 심볼 (예: "GRASSUSDT")
        period: 백테스트 기간 ("1w" or "1m")
    
    Returns:
        캐시 키 (예: "GRASSUSDT_1w_2025-11-20")
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{symbol}_{period}_{today}"


def evaluate_suitability(results: Dict) -> Tuple[str, float]:
    """
    백테스트 결과로 거래 적합성 판단
    
    평가 기준:
    1. 승률 (30점)
       - >=70%: 30점
       - >=50%: 20점
       - >=40%: 10점
    
    2. 수익률 (40점)
       - >=+5%: 40점
       - >=+2%: 30점
       - >=0%: 15점
    
    3. 최대 낙폭 MDD (20점)
       - <=3%: 20점
       - <=5%: 15점
       - <=10%: 10점
    
    4. 거래 횟수 (10점)
       - >=5회: 10점
       - >=3회: 5점
    
    최종 판단:
    - 적합: 70점 이상 + 승률>=50% + 수익률>=+2%
    - 주의 필요: 50점 이상
    - 부적합: 50점 미만
    
    Args:
        results: 백테스트 메트릭 딕셔너리
    
    Returns:
        Tuple[적합성 문자열, 점수]
    """
    score = 0.0
    
    # 1. 승률 평가 (30점)
    win_rate = results.get("win_rate", 0)
    if win_rate >= 70:
        score += 30
    elif win_rate >= 50:
        score += 20
    elif win_rate >= 40:
        score += 10
    
    # 2. 수익률 평가 (40점)
    pnl_pct = results.get("total_pnl_pct", 0)
    if pnl_pct >= 5:
        score += 40
    elif pnl_pct >= 2:
        score += 30
    elif pnl_pct >= 0:
        score += 15
    
    # 3. 최대 낙폭 평가 (20점)
    mdd = results.get("max_drawdown", 100)
    if mdd <= 3:
        score += 20
    elif mdd <= 5:
        score += 15
    elif mdd <= 10:
        score += 10
    
    # 4. 거래 횟수 평가 (10점)
    trades = results.get("total_trades", 0)
    if trades >= 5:
        score += 10
    elif trades >= 3:
        score += 5
    
    # 최종 적합성 판단
    if score >= 70 and win_rate >= 50 and pnl_pct >= 2:
        suitability = "적합"
    elif score >= 50:
        suitability = "주의 필요"
    else:
        suitability = "부적합"
    
    logger.info(f"[SUITABILITY] {suitability} ({score:.0f}점) - "
                f"승률={win_rate:.1f}%, 수익률={pnl_pct:+.2f}%, MDD={mdd:.1f}%")
    
    return suitability, score


def generate_reason(results: Dict) -> str:
    """
    적합성 판단 근거 생성
    
    Args:
        results: 백테스트 메트릭
    
    Returns:
        근거 문자열 (예: "승률 60.0%, 수익률 +5.20%, 거래 10회, MDD 3.5%")
    """
    win_rate = results.get("win_rate", 0)
    pnl_pct = results.get("total_pnl_pct", 0)
    trades = results.get("total_trades", 0)
    mdd = results.get("max_drawdown", 0)
    
    return (
        f"승률 {win_rate:.1f}%, "
        f"수익률 {pnl_pct:+.2f}%, "
        f"거래 {trades}회, "
        f"MDD {mdd:.1f}%"
    )


@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(
    symbol: str,
    period: str = "1w"  # "1w" (1주) or "1m" (1달)
):
    """
    코인 심볼의 거래 적합성 평가 (백테스팅)
    
    API 최적화:
    1. 메모리 캐싱: 동일 심볼+기간+날짜 → 캐시 반환 (API 호출 0번)
    2. 우선순위 큐: 최대 3개 동시 백테스트 실행 (Rate Limit 방지)
    
    Args:
        symbol: 코인 심볼 (예: "GRASSUSDT")
        period: 백테스트 기간 ("1w" = 1주, "1m" = 1달)
    
    Returns:
        {
            "success": true,
            "cached": true/false,  # 캐시 여부
            "data": {
                "symbol": "GRASSUSDT",
                "period": "1w",
                "suitability": "적합" | "부적합" | "주의 필요",
                "score": 75.5,
                "reason": "승률 60%, 수익률 +5.2%, 거래 10회, MDD 3.5%",
                "metrics": {
                    "total_pnl": 520.0,
                    "total_pnl_pct": 5.2,
                    "total_trades": 10,
                    "win_rate": 60.0,
                    "winning_trades": 6,
                    "losing_trades": 4,
                    "avg_win": 87.0,
                    "avg_loss": -45.0,
                    "profit_factor": 1.93,
                    "max_drawdown": 3.5,
                    "sharpe_ratio": 1.2
                }
            }
        }
    """
    # ========================================
    # 1. 캐시 확인 (메모리)
    # ========================================
    cache_key = get_cache_key(symbol, period)
    
    if cache_key in backtest_result_cache:
        logger.info(f"✅ [CACHE HIT] {cache_key}")
        return {
            "success": True,
            "cached": True,
            "data": backtest_result_cache[cache_key]
        }
    
    logger.info(f"🔄 [CACHE MISS] {cache_key} - 백테스트 실행")
    
    # ========================================
    # 2. 우선순위 큐 (동시 실행 제한)
    # ========================================
    async with backtest_semaphore:
        try:
            # 3. 백테스트 기간 계산
            end_date = datetime.now()
            if period == "1w":
                start_date = end_date - timedelta(days=7)
            elif period == "1m":
                start_date = end_date - timedelta(days=30)
            else:
                return {
                    "success": False,
                    "error": f"Invalid period: {period} (use '1w' or '1m')"
                }
            
            # 4. BacktestConfig 생성
            config = BacktestConfig(
                symbol=symbol,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                initial_balance=10000.0,
                leverage=50,
                commission_rate=0.0004,
                slippage_rate=0.0001,
            )
            
            # 5. Orchestrator 생성 (Alpha 전략)
            from backend.app_main import shared_binance_client  # 전역 공유 클라이언트
            
            orchestrator = StrategyOrchestrator(
                binance_client=shared_binance_client,
                config=OrchestratorConfig(
                    symbol=symbol,
                    leverage=50,
                    order_quantity=0.001,
                    enable_trading=False,  # 백테스트는 실거래 안함
                )
            )
            
            # 6. 백테스트 실행
            logger.info(f"[BACKTEST] 시작: {symbol} ({period}) - {config.start_date} ~ {config.end_date}")
            
            adapter = BacktestAdapter(shared_binance_client)
            results = adapter.run_backtest(orchestrator, config)
            
            logger.info(f"[BACKTEST] 완료: {symbol} - {results.get('total_trades', 0)}건 거래")
            
            # 7. 적합성 평가
            suitability, score = evaluate_suitability(results)
            reason = generate_reason(results)
            
            # 8. 응답 데이터 생성
            response_data = {
                "symbol": symbol,
                "period": period,
                "suitability": suitability,
                "score": score,
                "reason": reason,
                "metrics": results
            }
            
            # ========================================
            # 9. 캐시 저장 (LRU: 가장 오래된 항목 제거)
            # ========================================
            if len(backtest_result_cache) >= MAX_CACHE_SIZE:
                oldest_key = next(iter(backtest_result_cache))
                removed = backtest_result_cache.pop(oldest_key)
                logger.info(f"[CACHE] LRU 제거: {oldest_key}")
            
            backtest_result_cache[cache_key] = response_data
            logger.info(f"💾 [CACHE SAVED] {cache_key} (캐시 크기: {len(backtest_result_cache)})")
            
            return {
                "success": True,
                "cached": False,
                "data": response_data
            }
        
        except Exception as e:
            logger.error(f"❌ [BACKTEST ERROR] {symbol}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
```

---

### Phase 2: GUI 수정 (기존 계획 유지)

#### 2-1. 컬럼 명칭 변경

**파일**: `gui/widgets/ranking_table_widget.py` (line 27)

```python
# 변경 전
self.setHorizontalHeaderLabels(["선택", "랭크", "코인 심볼", "상승률%", "누적", "상승 유형"])

# ========================================
# 변경 후
# ========================================
self.setHorizontalHeaderLabels(["선택", "거래 적합성", "코인 심볼", "상승률%", "누적", "상승 유형"])
```

---

#### 2-2. 시그널 추가

**파일**: `gui/widgets/ranking_table_widget.py` (line 18-20)

```python
# 변경 전
class RankingTableWidget(QTableWidget):
    # 시그널 정의
    symbol_clicked = Signal(str)
    analyze_requested = Signal(str)  # 기존

# ========================================
# 변경 후
# ========================================
class RankingTableWidget(QTableWidget):
    # 시그널 정의
    symbol_clicked = Signal(str)
    analyze_requested = Signal(str)        # 기존: 2열 분석 요청
    backtest_requested = Signal(str)       # ✨ 새로: 백테스트 요청
```

---

#### 2-3. 데이터 구조 확장

**파일**: `gui/widgets/ranking_table_widget.py` (populate 메서드 내)

```python
def populate(self, items: List[Dict[str, Any]]):
    """
    데이터로 테이블 채우기
    
    Args:
        items: 랭킹 데이터 리스트
            각 item에 추가 필드:
            - backtest_status: "대기" | "분석중" | "적합" | "부적합" | "주의 필요"
            - backtest_score: 0~100 점수
    """
    # 기존 체크박스 참조 클리어
    self._checkboxes.clear()
    
    # 행 개수 설정
    self.setRowCount(len(items))
    
    for i, item in enumerate(items):
        # ========================================
        # 백테스트 상태 초기화 (없으면 기본값)
        # ========================================
        if "backtest_status" not in item:
            item["backtest_status"] = "대기"
        if "backtest_score" not in item:
            item["backtest_score"] = 0
        
        # ... 나머지 populate 로직 ...
```

---

#### 2-4. 거래 적합성 컬럼 렌더링

**파일**: `gui/widgets/ranking_table_widget.py` (populate 메서드 내, 컬럼 1 렌더링 부분)

```python
# ========================================
# 컬럼 1: 거래 적합성 (기존 "랭크" 위치)
# ========================================
status = item.get("backtest_status", "대기")
score = item.get("backtest_score", 0)

# 상태별 텍스트 & 색상
if status == "적합":
    text = f"✅ 적합 ({score:.0f})"
    color = "#03b662"  # 녹색
elif status == "부적합":
    text = f"❌ 부적합 ({score:.0f})"
    color = "#e16476"  # 빨강
elif status == "주의 필요":
    text = f"⚠️ 주의 ({score:.0f})"
    color = "#ff8c25"  # 주황
elif status == "분석중":
    text = "⏳ 분석중..."
    color = "#1e88e5"  # 파랑
else:  # "대기"
    text = "-"
    color = "#3c3c3c"  # 회색

# 셀 아이템 생성
suitability_item = QTableWidgetItem(text)
suitability_item.setTextAlignment(Qt.AlignCenter)
suitability_item.setForeground(QColor(color))
font = QFont()
font.setBold(True)
suitability_item.setFont(font)
self.setItem(i, 1, suitability_item)
```

---

#### 2-5. 클릭 이벤트 수정 (핵심!)

**파일**: `gui/widgets/ranking_table_widget.py` (line 267-278)

```python
# 변경 전
def _on_cell_clicked(self, row: int, col: int):
    symbol_widget = self.cellWidget(row, 2)
    if not symbol_widget:
        return
    
    symbol = symbol_widget.property("symbol")
    if not symbol:
        return
    
    if col == 2:  # 심볼 컬럼
        url = symbol_widget.property("url")
        if url:
            import webbrowser
            webbrowser.open(url)
    elif col in [3, 4, 5]:  # 상승률/누적/유형
        self.analyze_requested.emit(symbol)

# ========================================
# 변경 후
# ========================================
def _on_cell_clicked(self, row: int, col: int):
    symbol_widget = self.cellWidget(row, 2)
    if not symbol_widget:
        return
    
    symbol = symbol_widget.property("symbol")
    if not symbol:
        return
    
    if col == 2:  # 심볼 컬럼 - 바이낸스 페이지
        url = symbol_widget.property("url")
        if url:
            import webbrowser
            webbrowser.open(url)
    
    elif col in [3, 4, 5]:  # 상승률/누적/유형 - 분석 + 백테스트 동시 실행!
        print(f"[RANKING_TABLE] 📊 분석 + 백테스트 요청: {symbol}")
        
        # 1️⃣ 기존 분석 (2열 업데이트)
        self.analyze_requested.emit(symbol)
        
        # 2️⃣ 백테스트 실행 (컬럼 1 업데이트)
        self.backtest_requested.emit(symbol)
```

---

#### 2-6. main.py 연결

**파일**: `gui/main.py`

```python
# ========================================
# 1. Signal 연결 추가 (line 124 근처)
# ========================================
self.ranking_table.analyze_requested.connect(self._on_analyze_symbol)
self.ranking_table.backtest_requested.connect(self._on_backtest_requested)  # ✨ 추가


# ========================================
# 2. 백테스트 완료/실패 시그널 추가
# ========================================
class YONAMainWindow(QMainWindow):
    backtest_completed = Signal(str, str, float, dict)  # symbol, suitability, score, metrics
    backtest_failed = Signal(str, str)  # symbol, error

def __init__(self):
    super().__init__()
    # ... 기존 초기화 ...
    
    # 백테스트 시그널 연결
    self.backtest_completed.connect(self._on_backtest_completed)
    self.backtest_failed.connect(self._on_backtest_failed)


# ========================================
# 3. 백테스트 요청 핸들러
# ========================================
def _on_backtest_requested(self, symbol: str):
    """
    백테스트 시작 요청
    
    플로우:
    1. UI 상태 변경 (컬럼 1을 "분석중"으로)
    2. 백그라운드 스레드에서 API 호출
    3. 결과 수신 시 Signal로 UI 업데이트
    
    Args:
        symbol: 코인 심볼
    """
    print(f"[MAIN] 🔬 백테스트 시작: {symbol}")
    
    # 1. UI 상태 변경 (컬럼 1을 "분석중"으로)
    self._update_backtest_status(symbol, "분석중", 0)
    
    # 2. 백그라운드에서 백테스트 실행 (UI 블로킹 방지)
    def worker():
        try:
            print(f"[MAIN] 🌐 백테스트 API 호출: {symbol}")
            
            # API 호출 (타임아웃 30초 - 백테스트는 시간 소요)
            response = requests.get(
                f"{BASE_URL}/api/v1/backtest/suitability",
                params={"symbol": symbol, "period": "1w"},
                timeout=30
            )
            
            if response.ok:
                data = response.json().get("data", {})
                suitability = data.get("suitability", "부적합")
                score = data.get("score", 0)
                metrics = data.get("metrics", {})
                cached = response.json().get("cached", False)
                
                cache_msg = "캐시" if cached else "신규"
                print(f"[MAIN] ✅ 백테스트 완료 ({cache_msg}): {symbol} -> {suitability} ({score}점)")
                
                # UI 업데이트 (Signal 사용)
                self.backtest_completed.emit(symbol, suitability, score, metrics)
            else:
                error = f"API 오류 (status={response.status_code})"
                print(f"[MAIN] ❌ 백테스트 실패: {symbol} -> {error}")
                self.backtest_failed.emit(symbol, error)
        
        except requests.Timeout:
            error = "타임아웃 (30초 초과)"
            print(f"[MAIN] ⏱️ 백테스트 타임아웃: {symbol}")
            self.backtest_failed.emit(symbol, error)
        
        except Exception as e:
            error = str(e)
            print(f"[MAIN] ❌ 백테스트 예외: {symbol} -> {error}")
            self.backtest_failed.emit(symbol, error)
    
    # 데몬 스레드로 실행 (GUI 메인 스레드 블로킹 방지)
    threading.Thread(target=worker, daemon=True).start()


# ========================================
# 4. 백테스트 상태 업데이트 헬퍼
# ========================================
def _update_backtest_status(self, symbol: str, status: str, score: float):
    """
    백테스트 상태 업데이트 (랭킹 테이블 컬럼 1)
    
    Args:
        symbol: 코인 심볼
        status: "대기" | "분석중" | "적합" | "부적합" | "주의 필요"
        score: 0~100 점수
    """
    # 테이블에서 해당 심볼 행 찾기
    for row in range(self.ranking_table.rowCount()):
        symbol_widget = self.ranking_table.cellWidget(row, 2)
        if symbol_widget and symbol_widget.property("symbol") == symbol:
            # 컬럼 1 (거래 적합성) 업데이트
            if status == "적합":
                text = f"✅ 적합 ({score:.0f})"
                color = "#03b662"
            elif status == "부적합":
                text = f"❌ 부적합 ({score:.0f})"
                color = "#e16476"
            elif status == "주의 필요":
                text = f"⚠️ 주의 ({score:.0f})"
                color = "#ff8c25"
            elif status == "분석중":
                text = "⏳ 분석중..."
                color = "#1e88e5"
            else:  # "대기"
                text = "-"
                color = "#3c3c3c"
            
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(QColor(color))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.ranking_table.setItem(row, 1, item)
            break


# ========================================
# 5. 백테스트 완료 핸들러 (UI 스레드)
# ========================================
def _on_backtest_completed(self, symbol: str, suitability: str, score: float, metrics: dict):
    """
    백테스트 완료 처리 (UI 스레드에서 실행)
    
    Args:
        symbol: 코인 심볼
        suitability: 적합성 ("적합" | "부적합" | "주의 필요")
        score: 점수 (0~100)
        metrics: 백테스트 메트릭 딕셔너리
    """
    print(f"[MAIN] 📊 백테스트 결과 UI 업데이트: {symbol} -> {suitability} ({score}점)")
    self._update_backtest_status(symbol, suitability, score)


# ========================================
# 6. 백테스트 실패 핸들러
# ========================================
def _on_backtest_failed(self, symbol: str, error: str):
    """
    백테스트 실패 처리
    
    Args:
        symbol: 코인 심볼
        error: 에러 메시지
    """
    print(f"[MAIN] ❌ 백테스트 실패 UI 업데이트: {symbol} -> {error}")
    
    # 상태를 "대기"로 복원
    self._update_backtest_status(symbol, "대기", 0)
    
    # 사용자에게 경고 메시지
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.warning(
        self,
        "백테스트 실패",
        f"{symbol} 백테스트 실패:\n{error}"
    )
```

---

## 📊 API 최적화 효과

### 시나리오: 10명이 GRASSUSDT 클릭

| 항목 | 최적화 전 | 최적화 후 | 개선 |
|------|-----------|-----------|------|
| **총 API 호출** | 110회 (11×10) | 11회 (첫 요청만) | **90% 감소** |
| **총 소요 시간** | 50초 (5×10) | 5.09초 (첫 5초 + 나머지 0.01×9) | **90% 단축** |
| **캐시 히트율** | 0% | 90% (10명 중 9명) | - |
| **서버 부하** | 지속적 | 첫 요청만 | **일시적** |

---

### 병렬 요청 시나리오: 3명이 동시에 서로 다른 심볼 클릭

```
사용자 A: GRASSUSDT 클릭
사용자 B: BTCUSDT 클릭 (동시)
사용자 C: ETHUSDT 클릭 (동시)

최적화 전:
  - API 호출: 33회 (11×3)
  - 동시 실행: 제한 없음 → Rate Limit 위험

최적화 후:
  - API 호출: 33회 (11×3) - 캐시 미스
  - 동시 실행: 최대 3개까지만 (Semaphore)
  - 대기 큐: 없음 (3개 이하)
```

---

## 🎯 사용자 플로우 (최종)

### 시나리오 1: 첫 요청 (캐시 미스)

```
1. 사용자가 GRASSUSDT의 "상승률%" 클릭

2. 즉시 실행:
   ① 우측 2열 분석 시작 (기존 기능)
   ② "거래 적합성" 컬럼: "⏳ 분석중..." 표시

3. 백엔드 처리 (5~15초):
   - 캐시 미스 → API 호출 (11~41회)
   - 백테스트 실행
   - 적합성 평가 (승률, 수익률, MDD)
   - 결과 캐싱

4. UI 업데이트:
   - "거래 적합성" 컬럼: "✅ 적합 (75점)"
```

---

### 시나리오 2: 재요청 (캐시 히트)

```
1. 같은 날 GRASSUSDT의 "누적" 재클릭

2. 즉시 실행:
   ① 우측 2열 분석 (기존 기능)
   ② "거래 적합성" 컬럼: "⏳ 분석중..." (잠깐)

3. 백엔드 처리 (0.01초):
   - 캐시 히트 ✅ → API 호출 0번
   - 캐시된 결과 즉시 반환

4. UI 업데이트 (즉시):
   - "거래 적합성" 컬럼: "✅ 적합 (75점)"
```

---

## 📝 수정 파일 목록 (최종)

### 백엔드

```
1. backend/app_main.py
   - /api/v1/backtest/suitability 엔드포인트 추가
   - 메모리 캐싱 (backtest_result_cache)
   - 우선순위 큐 (backtest_semaphore)
   - evaluate_suitability() 함수
   - generate_reason() 함수
```

### 프론트엔드

```
2. gui/widgets/ranking_table_widget.py
   - 컬럼 명칭 변경 (line 27): "랭크" → "거래 적합성"
   - backtest_requested Signal 추가 (line 20)
   - populate() 메서드 수정: backtest_status/score 초기화
   - _on_cell_clicked() 수정 (line 267): col 3/4/5 → 동시 실행
   - 거래 적합성 컬럼 렌더링 (populate 내)

3. gui/main.py
   - backtest_completed/failed Signal 추가
   - Signal 연결 (line 124)
   - _on_backtest_requested() 구현
   - _update_backtest_status() 구현
   - _on_backtest_completed() 구현
   - _on_backtest_failed() 구현
```

---

## 🚀 구현 우선순위

### MVP (최소 기능 - 2일)

```
Day 1: 백엔드
  ⬜ API 엔드포인트 추가 (캐싱 + 우선순위 큐)
  ⬜ evaluate_suitability() 구현
  ⬜ generate_reason() 구현
  ⬜ 테스트 (Postman/curl)

Day 2: 프론트엔드
  ⬜ ranking_table_widget.py 수정
  ⬜ main.py 핸들러 구현
  ⬜ 통합 테스트
```

---

### 추가 최적화 (선택 - 1~2일)

```
Phase 2:
  ⬜ 파일 캐싱 (영구 저장)
  ⬜ 병렬 데이터 로딩 (asyncio)
  ⬜ 상세 다이얼로그 (메트릭 표시)

Phase 3 (프로덕션):
  ⬜ Redis 캐싱
  ⬜ 캐시 관리 API (/clear, /stats)
```

---

## 📊 예상 성능

### API 호출 수 (1주 백테스트 기준)

| 상황 | 기존 | 최적화 후 | 감소율 |
|------|------|-----------|--------|
| 첫 요청 | 11회 | 11회 | 0% |
| 재요청 (동일 심볼, 동일 날짜) | 11회 | **0회** | **100%** |
| 10명 요청 (동일 심볼) | 110회 | 11회 | **90%** |
| 100명 요청 (동일 심볼) | 1,100회 | 11회 | **99%** |

### 응답 시간

| 상황 | 기존 | 최적화 후 | 단축율 |
|------|------|-----------|--------|
| 첫 요청 (1주) | 5초 | 5초 | 0% |
| 재요청 (캐시 히트) | 5초 | **0.01초** | **99.8%** |

---

## ✅ 최종 확인

### 사용자 의도 반영

| 요구사항 | 구현 계획 | 상태 |
|----------|-----------|------|
| "랭크" → "거래 적합성" 명칭 변경 | ranking_table_widget.py line 27 | ✅ |
| col 3/4/5 클릭 시 2열 분석 | analyze_requested 유지 | ✅ |
| col 3/4/5 클릭 시 백테스트 실행 | backtest_requested 추가 | ✅ |
| 백테스트 결과를 "거래 적합성"에 표시 | _update_backtest_status 구현 | ✅ |
| 우리 앱 전략 기준 적합성 판단 | Alpha Orchestrator 사용 | ✅ |
| **API 부하 최소화** | **메모리 캐싱 + 우선순위 큐** | **✅** |

---

## 🎊 핵심 개선사항

### 기존 계획 대비

1. ✅ **메모리 캐싱 추가**
   - 동일 심볼+기간+날짜 → API 호출 0번
   - LRU 방식 (최대 100개)

2. ✅ **우선순위 큐 추가**
   - 최대 3개 동시 백테스트
   - Rate Limit 방지

3. ✅ **캐시 여부 표시**
   - API 응답에 `"cached": true/false` 추가
   - 로그에 캐시 히트/미스 구분

4. ✅ **타임아웃 처리**
   - 30초 타임아웃 (백테스트는 시간 소요)
   - 타임아웃 시 사용자 안내

---

**API 부하 최적화가 반영된 백테스팅 '거래 적합성' 구현 계획입니다!** 🚀

**주요 개선:**
- ✅ API 호출 90% 감소 (캐싱)
- ✅ 응답 속도 500배 향상 (캐시 히트 시)
- ✅ Rate Limit 방지 (우선순위 큐)
- ✅ 일시적 부하 (첫 요청만)

**구현 준비 완료!** ✅

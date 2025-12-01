# 백테스팅 통합 기능 구현 계획서

**생성일**: 2025-11-20  
**사용자 의도 재확인 및 정확한 구현 계획**

---

## 📋 사용자 의도 정확 분석

### 🎯 사용자가 원하는 것

#### 1. **UI 변경**
```
기존: ["선택", "랭크", "코인 심볼", "상승률%", "누적", "상승 유형"]
변경: ["선택", "거래 적합성", "코인 심볼", "상승률%", "누적", "상승 유형"]
                ^^^^^^^^
```
- **"랭크" → "거래 적합성"** 명칭 변경

#### 2. **클릭 동작 (핵심!)**

**사용자가 컬럼 3/4/5 (상승률%, 누적, 상승 유형) 클릭 시:**

```
클릭 → 2가지 작업 동시 또는 순차 실행

1️⃣ 기존 기능 유지: 2열 분석 (Coin Momentum & Chart)
   - 우측 2열의 추세 분석 위젯 업데이트
   - 타이밍 분석 차트 업데이트
   - API: /api/v1/live/analysis/entry

2️⃣ 새로운 기능 추가: 백테스팅 실행
   - 해당 코인으로 1주/1달 백테스트 실행
   - 우리 앱 엔진 전략 적합성 평가
   - 결과를 "거래 적합성" 컬럼에 표시
   - API: /api/v1/backtest/suitability
```

#### 3. **백테스트 결과 표시**

**"거래 적합성" 컬럼 (col 1) 상태 변화:**
```
초기 상태: "-" (대기)
    ↓
클릭 (col 3/4/5)
    ↓
"⏳ 분석중..." (백테스트 진행 중)
    ↓
"✅ 적합 (75점)" 또는 "❌ 부적합 (45점)"
```

---

## 🔧 구현 계획

### Phase 1: 백엔드 API 구현

#### 1-1. 백테스트 API 엔드포인트 추가

**파일**: `backend/app_main.py` 또는 새 라우터 파일

```python
from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
from backend.core.new_strategy.backtest_adapter import BacktestAdapter, BacktestConfig
from datetime import datetime, timedelta
from typing import Tuple

@app.get("/api/v1/backtest/suitability")
async def get_trading_suitability(
    symbol: str,
    period: str = "1w"  # "1w" or "1m"
):
    """
    코인 심볼의 거래 적합성 평가 (백테스팅)
    
    Args:
        symbol: 코인 심볼 (예: "GRASSUSDT")
        period: 백테스트 기간 ("1w" = 1주, "1m" = 1달)
    
    Returns:
        {
            "success": true,
            "data": {
                "symbol": "GRASSUSDT",
                "period": "1w",
                "suitability": "적합" | "부적합" | "주의 필요",
                "score": 75.5,  # 0~100
                "reason": "승률 60%, 수익률 +5.2%",
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
    try:
        # 1. 기간 계산
        end_date = datetime.now()
        if period == "1w":
            start_date = end_date - timedelta(days=7)
        else:  # "1m"
            start_date = end_date - timedelta(days=30)
        
        # 2. BacktestConfig 생성
        config = BacktestConfig(
            symbol=symbol,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            initial_balance=10000.0,
            leverage=50,
            commission_rate=0.0004,
            slippage_rate=0.0001,
        )
        
        # 3. Orchestrator 생성 (Alpha 전략 사용)
        orchestrator = StrategyOrchestrator(
            binance_client=shared_binance_client,  # 전역 공유 클라이언트
            config=OrchestratorConfig(
                symbol=symbol,
                leverage=50,
                order_quantity=0.001,
                enable_trading=False,  # 백테스트는 실거래 안함
            )
        )
        
        # 4. 백테스트 실행
        adapter = BacktestAdapter(shared_binance_client)
        results = adapter.run_backtest(orchestrator, config)
        
        # 5. 적합성 판단
        suitability, score = evaluate_suitability(results)
        reason = generate_reason(results)
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "suitability": suitability,
                "score": score,
                "reason": reason,
                "metrics": results
            }
        }
    
    except Exception as e:
        logger.error(f"Backtest failed for {symbol}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def evaluate_suitability(results: Dict) -> Tuple[str, float]:
    """
    백테스트 결과로 거래 적합성 판단
    
    기준:
    - 승률 >= 50%
    - 수익률 >= +2%
    - 최대 낙폭 <= 5%
    - 거래 횟수 >= 3회
    """
    score = 0.0
    
    # 승률 (30점)
    win_rate = results.get("win_rate", 0)
    if win_rate >= 70:
        score += 30
    elif win_rate >= 50:
        score += 20
    elif win_rate >= 40:
        score += 10
    
    # 수익률 (40점)
    pnl_pct = results.get("total_pnl_pct", 0)
    if pnl_pct >= 5:
        score += 40
    elif pnl_pct >= 2:
        score += 30
    elif pnl_pct >= 0:
        score += 15
    
    # 최대 낙폭 (20점)
    mdd = results.get("max_drawdown", 100)
    if mdd <= 3:
        score += 20
    elif mdd <= 5:
        score += 15
    elif mdd <= 10:
        score += 10
    
    # 거래 횟수 (10점)
    trades = results.get("total_trades", 0)
    if trades >= 5:
        score += 10
    elif trades >= 3:
        score += 5
    
    # 적합성 판단
    if score >= 70 and win_rate >= 50 and pnl_pct >= 2:
        suitability = "적합"
    elif score >= 50:
        suitability = "주의 필요"
    else:
        suitability = "부적합"
    
    return suitability, score


def generate_reason(results: Dict) -> str:
    """적합성 판단 근거 생성"""
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
```

---

### Phase 2: GUI 수정

#### 2-1. 컬럼 명칭 변경

**파일**: `gui/widgets/ranking_table_widget.py` (line 27)

```python
# 현재
self.setHorizontalHeaderLabels(["선택", "랭크", "코인 심볼", "상승률%", "누적", "상승 유형"])

# 변경
self.setHorizontalHeaderLabels(["선택", "거래 적합성", "코인 심볼", "상승률%", "누적", "상승 유형"])
```

---

#### 2-2. 데이터 구조 확장

**파일**: `gui/widgets/ranking_table_widget.py`

```python
def populate(self, items: List[Dict[str, Any]]):
    """데이터로 테이블 채우기"""
    # 각 item에 백테스트 상태 추가
    for item in items:
        if "backtest_status" not in item:
            item["backtest_status"] = "대기"  # 초기값
        if "backtest_score" not in item:
            item["backtest_score"] = 0
```

---

#### 2-3. 거래 적합성 컬럼 렌더링

**파일**: `gui/widgets/ranking_table_widget.py` (populate 메서드 내)

```python
# 거래 적합성 (컬럼 1) - 기존 "랭크" 위치
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

suitability_item = QTableWidgetItem(text)
suitability_item.setTextAlignment(Qt.AlignCenter)
suitability_item.setForeground(QColor(color))
font = QFont()
font.setBold(True)
suitability_item.setFont(font)
self.setItem(i, 1, suitability_item)
```

---

#### 2-4. 클릭 이벤트 수정 (핵심!)

**파일**: `gui/widgets/ranking_table_widget.py` (line 267-272)

```python
# 현재
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
    elif col in [3, 4, 5]:  # 상승률/누적/유형 - 분석 요청
        self.analyze_requested.emit(symbol)

# ========================================
# 변경 후
# ========================================

class RankingTableWidget(QTableWidget):
    # 시그널 정의
    symbol_clicked = Signal(str)
    analyze_requested = Signal(str)  # 기존
    backtest_requested = Signal(str)  # ✨ 새로 추가

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

#### 2-5. main.py 연결

**파일**: `gui/main.py`

```python
# Signal 연결 추가 (line 124 근처)
self.ranking_table.analyze_requested.connect(self._on_analyze_symbol)
self.ranking_table.backtest_requested.connect(self._on_backtest_requested)  # ✨ 추가

# 백테스트 완료 시그널 (UI 업데이트용)
class YONAMainWindow(QMainWindow):
    backtest_completed = Signal(str, str, float, dict)  # symbol, suitability, score, metrics
    backtest_failed = Signal(str, str)  # symbol, error

def __init__(self):
    # ...기존 코드...
    
    # Signal 연결
    self.backtest_completed.connect(self._on_backtest_completed)
    self.backtest_failed.connect(self._on_backtest_failed)

def _on_backtest_requested(self, symbol: str):
    """백테스트 시작 요청"""
    print(f"[MAIN] 🔬 백테스트 시작: {symbol}")
    
    # 1. UI 상태 변경 (컬럼 1을 "분석중"으로)
    self._update_backtest_status(symbol, "분석중", 0)
    
    # 2. 백그라운드에서 백테스트 실행
    def worker():
        try:
            print(f"[MAIN] 🌐 백테스트 API 호출: {symbol}")
            response = requests.get(
                f"{BASE_URL}/api/v1/backtest/suitability",
                params={"symbol": symbol, "period": "1w"},  # 1주일 백테스트
                timeout=30  # 백테스트는 시간 소요
            )
            
            if response.ok:
                data = response.json().get("data", {})
                suitability = data.get("suitability", "부적합")
                score = data.get("score", 0)
                metrics = data.get("metrics", {})
                
                print(f"[MAIN] ✅ 백테스트 완료: {symbol} -> {suitability} ({score}점)")
                
                # UI 업데이트 (Signal 사용)
                self.backtest_completed.emit(symbol, suitability, score, metrics)
            else:
                error = f"API 오류 (status={response.status_code})"
                print(f"[MAIN] ❌ 백테스트 실패: {symbol} -> {error}")
                self.backtest_failed.emit(symbol, error)
        
        except Exception as e:
            error = str(e)
            print(f"[MAIN] ❌ 백테스트 예외: {symbol} -> {error}")
            self.backtest_failed.emit(symbol, error)
    
    threading.Thread(target=worker, daemon=True).start()

def _update_backtest_status(self, symbol: str, status: str, score: float):
    """백테스트 상태 업데이트 (랭킹 테이블 컬럼 1)"""
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
            else:
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

def _on_backtest_completed(self, symbol: str, suitability: str, score: float, metrics: dict):
    """백테스트 완료 처리 (UI 스레드)"""
    print(f"[MAIN] 📊 백테스트 결과 UI 업데이트: {symbol} -> {suitability} ({score}점)")
    self._update_backtest_status(symbol, suitability, score)

def _on_backtest_failed(self, symbol: str, error: str):
    """백테스트 실패 처리"""
    print(f"[MAIN] ❌ 백테스트 실패 UI 업데이트: {symbol} -> {error}")
    self._update_backtest_status(symbol, "대기", 0)
    QMessageBox.warning(self, "백테스트 실패", f"{symbol} 백테스트 실패:\n{error}")
```

---

### Phase 3: 상세 결과 다이얼로그 (선택 사항)

#### 3-1. 거래 적합성 컬럼 클릭 시 상세 결과 표시

**파일**: `gui/widgets/ranking_table_widget.py`

```python
class RankingTableWidget(QTableWidget):
    backtest_detail_requested = Signal(str, dict)  # symbol, metrics

def _on_cell_clicked(self, row: int, col: int):
    # ...기존 코드...
    
    elif col == 1:  # 거래 적합성 컬럼 - 상세 결과 표시
        # 백테스트가 완료된 경우에만
        item = self.item(row, 1)
        if item and item.text() not in ["-", "⏳ 분석중..."]:
            # 상세 메트릭 조회 필요 (캐시 또는 API 재호출)
            self.backtest_detail_requested.emit(symbol, {})
```

**파일**: `gui/widgets/backtest_detail_dialog.py` (신규 생성)

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QPushButton

class BacktestDetailDialog(QDialog):
    """백테스트 상세 결과 다이얼로그"""
    
    def __init__(self, symbol: str, metrics: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{symbol} 백테스팅 결과")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 헤더
        header = QLabel(f"<h2>{symbol} 백테스팅 결과 (1주)</h2>")
        layout.addWidget(header)
        
        # 종합 평가
        suitability = metrics.get("suitability", "N/A")
        score = metrics.get("score", 0)
        summary = QLabel(f"<h3>종합 평가: {suitability} ({score:.0f}점)</h3>")
        layout.addWidget(summary)
        
        # 메트릭 테이블
        table = QTableWidget(8, 2)
        table.setHorizontalHeaderLabels(["항목", "값"])
        
        metrics_data = [
            ("총 수익률", f"{metrics.get('total_pnl_pct', 0):+.2f}%"),
            ("총 수익 (USDT)", f"{metrics.get('total_pnl', 0):+.2f}"),
            ("승률", f"{metrics.get('win_rate', 0):.1f}%"),
            ("총 거래", f"{metrics.get('total_trades', 0)}회"),
            ("승리/손실", f"{metrics.get('winning_trades', 0)}승 {metrics.get('losing_trades', 0)}패"),
            ("평균 수익", f"{metrics.get('avg_win', 0):+.2f} USDT"),
            ("평균 손실", f"{metrics.get('avg_loss', 0):+.2f} USDT"),
            ("최대 낙폭", f"{metrics.get('max_drawdown', 0):.2f}%"),
        ]
        
        for i, (key, value) in enumerate(metrics_data):
            table.setItem(i, 0, QTableWidgetItem(key))
            table.setItem(i, 1, QTableWidgetItem(value))
        
        layout.addWidget(table)
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
```

---

## 📊 사용자 플로우

### 시나리오: GRASSUSDT 백테스트

```
1. 사용자가 랭킹 테이블에서 GRASSUSDT 확인
   랭크: 1
   코인 심볼: GRASSUSDT
   상승률%: +230.90%
   누적: +087.04%
   상승 유형: 급등

2. 사용자가 "상승률%" 또는 "누적" 또는 "상승 유형" 클릭
   (col 3/4/5 중 아무거나)

3. 동시 실행:
   
   ① 우측 2열 분석 시작
      - "Coin Momentum & Chart - GRASSUSDT" 표시
      - 추세 분석 위젯 업데이트
      - 타이밍 차트 로드
   
   ② 백테스트 시작
      - "거래 적합성" 컬럼: "⏳ 분석중..." 표시
      - 백엔드에서 1주일 과거 데이터 로드
      - Alpha 전략으로 시뮬레이션 실행

4. 백테스트 완료 (5~15초 후)
   
   - "거래 적합성" 컬럼 업데이트:
     "✅ 적합 (75점)" 또는 "❌ 부적합 (45점)"

5. (선택) "거래 적합성" 컬럼 클릭
   
   → 상세 다이얼로그 표시
   - 승률, 수익률, MDD 등 상세 메트릭
```

---

## ⚙️ 구현 우선순위

### MVP (최소 기능 - 2~3일)

```
[Phase 1] 백엔드
  ✅ BacktestAdapter 확인 (이미 완료)
  ⬜ API 엔드포인트 추가 (/api/v1/backtest/suitability)
  ⬜ 적합성 판단 로직 구현 (evaluate_suitability)

[Phase 2] GUI
  ⬜ 컬럼 명칭 변경 (랭크 → 거래 적합성)
  ⬜ backtest_requested Signal 추가
  ⬜ 클릭 이벤트 수정 (col 3/4/5 → 분석 + 백테스트 동시)
  ⬜ _on_backtest_requested 핸들러 구현
  ⬜ _update_backtest_status UI 업데이트
```

### 추가 기능 (Phase 2 - 1~2일)

```
⬜ 상세 다이얼로그 구현
⬜ 1주/1달 백테스트 선택 옵션
⬜ 백테스트 결과 캐싱
```

---

## 🎯 최종 확인

### ✅ 사용자 의도 반영 확인

| 요구사항 | 구현 계획 |
|----------|-----------|
| "랭크" → "거래 적합성" 명칭 변경 | ✅ ranking_table_widget.py line 27 수정 |
| col 3/4/5 클릭 시 2열 분석 | ✅ 기존 analyze_requested 유지 |
| col 3/4/5 클릭 시 백테스트 실행 | ✅ backtest_requested 추가 |
| 백테스트 결과를 "거래 적합성"에 표시 | ✅ _update_backtest_status 구현 |
| 우리 앱 전략 기준 적합성 판단 | ✅ Alpha Orchestrator 사용 |

### 📋 수정 파일 목록

```
백엔드:
1. backend/app_main.py (또는 새 라우터)
   - /api/v1/backtest/suitability 엔드포인트 추가

프론트엔드:
2. gui/widgets/ranking_table_widget.py
   - 컬럼 명칭 변경 (line 27)
   - backtest_requested Signal 추가
   - populate() 메서드 수정 (거래 적합성 렌더링)
   - _on_cell_clicked() 수정 (col 3/4/5 → 동시 실행)

3. gui/main.py
   - backtest_completed/failed Signal 추가
   - _on_backtest_requested() 구현
   - _update_backtest_status() 구현
   - _on_backtest_completed() 구현
   - _on_backtest_failed() 구현

선택사항:
4. gui/widgets/backtest_detail_dialog.py (신규)
   - 상세 결과 다이얼로그
```

---

## 🚀 예상 구현 기간

- **MVP**: 2~3일
  - 백엔드 API: 1일
  - GUI 통합: 1일
  - 테스트: 0.5일

- **완전 구현**: 3~4일
  - MVP + 상세 다이얼로그 + 캐싱

---

**사용자 의도가 정확하게 반영된 구현 계획입니다!** ✅

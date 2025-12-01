# GUI Alpha/Beta/Gamma 미구현 검증 보고서

**작성 시각**: 2025-11-19  
**검증 결과**: ❌ GUI에 Alpha만 구현, Beta/Gamma 미구현

---

## 1. 검증 요약

**사용자 보고 내용**: "GUI에 'Alpha'만 구현되어 있고, 'Beta', 'Gamma'는 구현되어 있지 않아!!"

**검증 결과**: ✅ **정확함** - GUI 코드에 NewModular만 생성되어 있음

---

## 2. GUI 코드 분석

### 2.1 MiddleSessionWidget 클래스 (Line 918-1098)
**파일**: `gui/widgets/footer_engines_widget.py`

**현재 구현 상태**:
```python
class MiddleSessionWidget(QWidget):
    """하단 푸터 - 알파, 베타, 감마 3개 자동매매 엔진"""
    
    def _init_ui(self):
        # ...
        
        # 1. NewModular 엔진 ← 오직 이것만 생성됨
        self.newmodular_engine = TradingEngineWidget("NewModular", "#9C27B0", self)
        self.newmodular_engine.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #7B1FA2, stop:1 #9C27B0);
                border: 2px solid #CE93D8;
                border-radius: 12px;
            }
        """)
        self.newmodular_engine.start_signal.connect(self._on_engine_start)
        self.newmodular_engine.stop_signal.connect(self._on_engine_stop)
        main_layout.addWidget(self.newmodular_engine)
        
        # Alpha/Beta/Gamma 위젯 생성 코드 ❌ 없음
```

---

## 3. 문제점 상세 분석

### 3.1 누락된 위젯 생성 코드

**필요한 코드** (미구현):
```python
# 2. Alpha 엔진 (❌ 없음)
self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
self.alpha_engine.start_signal.connect(self._on_engine_start)
self.alpha_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.alpha_engine)

# 3. Beta 엔진 (❌ 없음)
self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
self.beta_engine.start_signal.connect(self._on_engine_start)
self.beta_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.beta_engine)

# 4. Gamma 엔진 (❌ 없음)
self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
self.gamma_engine.start_signal.connect(self._on_engine_start)
self.gamma_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.gamma_engine)
```

---

### 3.2 존재하는 참조 코드 (Line 971-976, 1051-1073)

**모순 발견**: GUI 코드에 `self.alpha_engine`, `self.beta_engine`, `self.gamma_engine` 참조가 존재하지만 **위젯 생성 코드는 없음**

**코드 예시 (Line 971-977)**:
```python
def handle_message(self, message: Dict[str, Any]):
    msg_type = message.get("type")
    engine_name = message.get("engine", "")
    
    if msg_type == "ENGINE_ENERGY_ANALYSIS":
        data = message.get("data", {})
        if engine_name == "Alpha":
            self.alpha_engine.update_energy_analysis(data)  # ← self.alpha_engine 참조
        elif engine_name == "Beta":
            self.beta_engine.update_energy_analysis(data)   # ← self.beta_engine 참조
        elif engine_name == "Gamma":
            self.gamma_engine.update_energy_analysis(data)  # ← self.gamma_engine 참조
        elif engine_name == "NewModular":
            self.newmodular_engine.update_energy_analysis(data)
```

**추가 참조 위치**:
- Line 972: `self.alpha_engine.update_energy_analysis(data)`
- Line 974: `self.beta_engine.update_energy_analysis(data)`
- Line 976: `self.gamma_engine.update_energy_analysis(data)`
- Line 984: `self.alpha_engine._add_trade_message(msg_text)`
- Line 986: `self.beta_engine._add_trade_message(msg_text)`
- Line 988: `self.gamma_engine._add_trade_message(msg_text)`
- Line 996: `self.alpha_engine._add_risk_message(msg_text)`
- Line 998: `self.beta_engine._add_risk_message(msg_text)`
- Line 1000: `self.gamma_engine._add_risk_message(msg_text)`
- Line 1014: `self.alpha_engine.add_trade_record(...)`
- Line 1016: `self.beta_engine.add_trade_record(...)`
- Line 1018: `self.gamma_engine.add_trade_record(...)`
- Line 1026: `self.alpha_engine.update_stats(data)`
- Line 1028: `self.beta_engine.update_stats(data)`
- Line 1030: `self.gamma_engine.update_stats(data)`
- Line 1038: `self.alpha_engine.set_status(is_running)`
- Line 1040: `self.beta_engine.set_status(is_running)`
- Line 1042: `self.gamma_engine.set_status(is_running)`
- Line 1069: `self.alpha_engine.handle_funds_returned(...)`
- Line 1071: `self.beta_engine.handle_funds_returned(...)`
- Line 1073: `self.gamma_engine.handle_funds_returned(...)`

**결과**: 위젯이 생성되지 않았으므로 **AttributeError** 발생 가능

---

### 3.3 get_engine_status() 메서드 (Line 1082-1085)

**현재 코드**:
```python
def get_engine_status(self) -> Dict[str, bool]:
    """각 엔진의 실행 상태 반환"""
    return {
        "NewModular": self.newmodular_engine.is_running
        # Alpha/Beta/Gamma ❌ 없음
    }
```

**필요한 코드**:
```python
def get_engine_status(self) -> Dict[str, bool]:
    """각 엔진의 실행 상태 반환"""
    return {
        "Alpha": self.alpha_engine.is_running,
        "Beta": self.beta_engine.is_running,
        "Gamma": self.gamma_engine.is_running
    }
```

---

## 4. Backend vs GUI 불일치

### 4.1 Backend (engine_manager.py)
✅ **구현 완료** (Line 57-59):
```python
def _init_engines(self):
    """Alpha, Beta, Gamma 엔진 초기화"""
    self.engines["Alpha"] = AlphaStrategy()   # ✅
    self.engines["Beta"] = BetaStrategy()     # ✅
    self.engines["Gamma"] = GammaStrategy()   # ✅
```

### 4.2 GUI (footer_engines_widget.py)
❌ **미구현** (Line 937-949):
```python
def _init_ui(self):
    # ...
    # 1. NewModular 엔진만 생성됨
    self.newmodular_engine = TradingEngineWidget("NewModular", "#9C27B0", self)
    main_layout.addWidget(self.newmodular_engine)
    
    # Alpha/Beta/Gamma 위젯 생성 ❌ 없음
```

---

## 5. 예상 동작 분석

### 5.1 현재 GUI 실행 시
1. **표시되는 엔진**: NewModular만 (보라색)
2. **Alpha/Beta/Gamma 버튼**: ❌ 없음
3. **에러 가능성**: Backend에서 "Alpha" 메시지 전송 시 `AttributeError: 'MiddleSessionWidget' object has no attribute 'alpha_engine'`

### 5.2 Backend 메시지 전송 시나리오
```python
# Backend (engine_manager.py)
self._send_message(
    "ENGINE_STATS_UPDATE",
    engine="Alpha",  # ← "Alpha" 엔진명 전송
    data={...}
)

# GUI (footer_engines_widget.py - Line 1026)
if engine_name == "Alpha":
    self.alpha_engine.update_stats(data)  # ← AttributeError 발생 가능
```

---

## 6. 필요한 수정 사항

### 6.1 _init_ui() 메서드 수정 (Line 928-952)

**Before**:
```python
def _init_ui(self):
    main_layout = QHBoxLayout(self)
    # ...
    
    # 1. NewModular 엔진
    self.newmodular_engine = TradingEngineWidget("NewModular", "#9C27B0", self)
    self.newmodular_engine.start_signal.connect(self._on_engine_start)
    self.newmodular_engine.stop_signal.connect(self._on_engine_stop)
    main_layout.addWidget(self.newmodular_engine)
    
    main_layout.setStretchFactor(self.newmodular_engine, 1)
```

**After** (필요한 수정):
```python
def _init_ui(self):
    main_layout = QHBoxLayout(self)
    # ...
    
    # 1. Alpha 엔진
    self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
    self.alpha_engine.setStyleSheet("""
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #388E3C, stop:1 #4CAF50);
            border: 2px solid #81C784;
            border-radius: 12px;
        }
    """)
    self.alpha_engine.start_signal.connect(self._on_engine_start)
    self.alpha_engine.stop_signal.connect(self._on_engine_stop)
    main_layout.addWidget(self.alpha_engine)
    
    # 2. Beta 엔진
    self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
    self.beta_engine.setStyleSheet("""
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #1976D2, stop:1 #2196F3);
            border: 2px solid #64B5F6;
            border-radius: 12px;
        }
    """)
    self.beta_engine.start_signal.connect(self._on_engine_start)
    self.beta_engine.stop_signal.connect(self._on_engine_stop)
    main_layout.addWidget(self.beta_engine)
    
    # 3. Gamma 엔진
    self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
    self.gamma_engine.setStyleSheet("""
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #F57C00, stop:1 #FF9800);
            border: 2px solid #FFB74D;
            border-radius: 12px;
        }
    """)
    self.gamma_engine.start_signal.connect(self._on_engine_start)
    self.gamma_engine.stop_signal.connect(self._on_engine_stop)
    main_layout.addWidget(self.gamma_engine)
    
    # 너비 비율 (1:1:1)
    main_layout.setStretchFactor(self.alpha_engine, 1)
    main_layout.setStretchFactor(self.beta_engine, 1)
    main_layout.setStretchFactor(self.gamma_engine, 1)
```

---

### 6.2 get_engine_status() 메서드 수정 (Line 1082-1085)

**Before**:
```python
def get_engine_status(self) -> Dict[str, bool]:
    """각 엔진의 실행 상태 반환"""
    return {
        "NewModular": self.newmodular_engine.is_running
    }
```

**After**:
```python
def get_engine_status(self) -> Dict[str, bool]:
    """각 엔진의 실행 상태 반환"""
    return {
        "Alpha": self.alpha_engine.is_running,
        "Beta": self.beta_engine.is_running,
        "Gamma": self.gamma_engine.is_running
    }
```

---

### 6.3 start_all_engines() 메서드 수정 (Line 1087-1090)

**Before**:
```python
def start_all_engines(self):
    """모든 엔진 시작"""
    if not self.newmodular_engine.is_running:
        self.newmodular_engine.toggle_button.setChecked(True)
        self.newmodular_engine._on_toggle_clicked()
```

**After**:
```python
def start_all_engines(self):
    """모든 엔진 시작"""
    for engine in [self.alpha_engine, self.beta_engine, self.gamma_engine]:
        if not engine.is_running:
            engine.toggle_button.setChecked(True)
            engine._on_toggle_clicked()
```

---

### 6.4 stop_all_engines() 메서드 수정 (Line 1092-1095)

**Before**:
```python
def stop_all_engines(self):
    """모든 엔진 정지"""
    if self.newmodular_engine.is_running:
        self.newmodular_engine.toggle_button.setChecked(False)
        self.newmodular_engine._on_toggle_clicked()
```

**After**:
```python
def stop_all_engines(self):
    """모든 엔진 정지"""
    for engine in [self.alpha_engine, self.beta_engine, self.gamma_engine]:
        if engine.is_running:
            engine.toggle_button.setChecked(False)
            engine._on_toggle_clicked()
```

---

## 7. 수정 파일 목록

| 파일 | 수정 위치 | 수정 내용 |
|------|----------|----------|
| `gui/widgets/footer_engines_widget.py` | Line 928-952 | `_init_ui()`: NewModular 삭제, Alpha/Beta/Gamma 위젯 생성 |
| `gui/widgets/footer_engines_widget.py` | Line 1082-1085 | `get_engine_status()`: Alpha/Beta/Gamma 상태 반환 |
| `gui/widgets/footer_engines_widget.py` | Line 1087-1090 | `start_all_engines()`: 3개 엔진 시작 |
| `gui/widgets/footer_engines_widget.py` | Line 1092-1095 | `stop_all_engines()`: 3개 엔진 정지 |

**총 수정 위치**: 4곳 (모두 동일 파일)

---

## 8. 예상 구현 시간

| 단계 | 작업 | 예상 시간 |
|------|------|----------|
| 1 | `_init_ui()` 메서드 수정 (NewModular 삭제, Alpha/Beta/Gamma 생성) | 5분 |
| 2 | `get_engine_status()` 메서드 수정 | 1분 |
| 3 | `start_all_engines()` 메서드 수정 | 1분 |
| 4 | `stop_all_engines()` 메서드 수정 | 1분 |
| **총계** | | **8분** |

---

## 9. 검증 결과 요약

### 9.1 사용자 보고 정확성
✅ **100% 정확** - GUI에 Alpha만 구현되어 있고 Beta/Gamma는 미구현

**정확한 상황**:
- GUI에 "NewModular" 위젯만 생성됨
- `self.alpha_engine`, `self.beta_engine`, `self.gamma_engine` 참조는 존재하지만 위젯 생성 코드 없음
- Backend에는 Alpha/Beta/Gamma 엔진이 정상 구현됨 (engine_manager.py)
- **Frontend-Backend 불일치 상태**

### 9.2 Backend 상태
✅ **구현 완료**:
- `alpha_strategy.py` ✅
- `beta_strategy.py` ✅
- `gamma_strategy.py` ✅
- `engine_manager.py` ✅ (Alpha/Beta/Gamma 초기화)

### 9.3 GUI 상태
❌ **미구현**:
- `self.alpha_engine` 위젯 생성 ❌
- `self.beta_engine` 위젯 생성 ❌
- `self.gamma_engine` 위젯 생성 ❌
- `get_engine_status()` Alpha/Beta/Gamma 추가 ❌
- `start_all_engines()` 3개 엔진 시작 ❌
- `stop_all_engines()` 3개 엔진 정지 ❌

---

## 10. 다음 단계 (보고만 함)

### 10.1 즉시 수정 필요 항목
1. **GUI 위젯 생성**: `_init_ui()` 메서드에 Alpha/Beta/Gamma 위젯 추가
2. **NewModular 제거**: `self.newmodular_engine` 관련 코드 삭제
3. **메서드 수정**: `get_engine_status()`, `start_all_engines()`, `stop_all_engines()`

### 10.2 테스트 계획 (수정 후)
1. GUI 실행 → Alpha/Beta/Gamma 버튼 3개 표시 확인
2. 각 엔진 시작 → Backend 연동 확인
3. 메시지 수신 → `AttributeError` 발생하지 않음 확인

---

## 11. 결론

✅ **검증 완료**

**사용자 보고**: "GUI에 'Alpha'만 구현되어 있고, 'Beta', 'Gamma'는 구현되어 있지 않아!!"  
**검증 결과**: ✅ **정확함** (정확히는 NewModular만 있고 Alpha도 없음)

**현재 상태**:
- Backend: Alpha/Beta/Gamma ✅ 구현 완료
- GUI: NewModular만 표시, Alpha/Beta/Gamma ❌ 미구현
- 불일치: Frontend-Backend 불일치 상태

**수정 필요**: `gui/widgets/footer_engines_widget.py` 파일 4곳 수정 (8분 예상)

**보고 상태**: ✅ **검증 완료, 수정은 보류** (사용자 지시 대기 중)

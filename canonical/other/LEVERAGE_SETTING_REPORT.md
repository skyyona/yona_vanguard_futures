# 레버리지 설정 방식 검증 보고서

## 📋 검증 일시
- **날짜**: 2025년 11월 18일
- **시각**: 20:55 (KST)

---

## 🔍 사용자 질문
> "각 엔진에 '레버리지' 설정에 대한 부분이 '하드 코딩'으로 고정된 것 같아 보이는데!!! 사실인거야?"

---

## ✅ 검증 결과 요약

### **결론: 반은 맞고, 반은 틀립니다**

1. ✅ **초기값은 하드코딩**: 각 엔진 초기화 시 레버리지가 코드에 고정되어 있습니다
2. ✅ **런타임 변경 가능**: GUI 슬라이더를 통해 실시간으로 변경 가능합니다
3. ✅ **데이터베이스 저장**: 변경된 레버리지는 DB에 저장되어 다음 실행 시 복원됩니다

---

## 📊 상세 검증 내역

### 1. 초기 레버리지 값 (하드코딩)

#### Alpha 엔진
```python
# backend/core/strategies/alpha_strategy.py (Line 24-26)
self.config.update({
    "capital_allocation": 100.0,
    "leverage": 5,  # ← 하드코딩된 초기값
    ...
})
```
- **초기값**: 5x (고정)
- **위치**: `alpha_strategy.py` __init__ 메서드

#### Beta 엔진
```python
# backend/core/strategies/beta_strategy.py (Line 21-23)
self.config.update({
    "capital_allocation": 200.0,
    "leverage": 3,  # ← 하드코딩된 초기값
    ...
})
```
- **초기값**: 3x (고정)
- **위치**: `beta_strategy.py` __init__ 메서드

#### Gamma 엔진
```python
# backend/core/strategies/gamma_strategy.py (Line 22-24)
self.config.update({
    "capital_allocation": 300.0,
    "leverage": 2,  # ← 하드코딩된 초기값
    ...
})
```
- **초기값**: 2x (고정)
- **위치**: `gamma_strategy.py` __init__ 메서드

**✅ 사실**: 각 엔진의 초기 레버리지는 **코드에 하드코딩**되어 있습니다.

---

### 2. 런타임 레버리지 변경 기능

#### GUI 슬라이더
```python
# gui/widgets/footer_engines_widget.py (Line 262-265)
self.leverage_slider = QSlider(Qt.Horizontal)
self.leverage_slider.setMinimum(1)
self.leverage_slider.setMaximum(50)
self.leverage_slider.setValue(1)  # 초기 GUI 값은 1x
```

**주의**: GUI 슬라이더의 초기값(1x)과 엔진의 실제 초기값(Alpha 5x, Beta 3x, Gamma 2x)이 **불일치**합니다!

#### 레버리지 변경 흐름

1. **사용자가 GUI 슬라이더 조작**
   ```python
   # Line 282
   self.leverage_slider.valueChanged.connect(self._on_leverage_changed)
   ```

2. **슬라이더 값 변경 → 라벨 업데이트**
   ```python
   # Line 721-724
   def _on_leverage_changed(self, value):
       """Leverage 슬라이더 값 변경 시"""
       self.leverage_value_label.setText(f"{value}x")
   ```

3. **Apply Settings 버튼 클릭 → 바이낸스 API 호출**
   ```python
   # Line 569-582
   # 1. 바이낸스에 레버리지 설정
   client = BinanceClient()
   result = client.set_leverage(self.selected_symbol, leverage)
   
   actual_leverage = result.get("leverage", leverage)
   
   # 2. 백엔드 API로 레버리지 동기화
   lev_sync = requests.post(
       f"{BASE_URL}/api/v1/engine/leverage",
       json={"engine": self.engine_name, "leverage": actual_leverage},
       timeout=5
   )
   
   # 3. GUI 변수 업데이트
   self.applied_leverage = actual_leverage
   ```

4. **백엔드에서 엔진 설정 업데이트**
   ```python
   # backend/api/routes.py (Line 280-292)
   @router.post("/engine/leverage")
   async def set_engine_leverage(request: EngineLeverageRequest, ...):
       await service.update_engine_leverage(request.engine, request.leverage)
       return {"status": "success", "message": f"{request.engine} 레버리지 {request.leverage}x 적용"}
   ```

5. **엔진 config 업데이트 및 DB 저장**
   ```python
   # backend/core/yona_service.py (Line 765-796)
   async def update_engine_leverage(self, engine_name: str, leverage: int):
       # 런타임 설정 반영
       engine.update_config({"leverage": leverage})
       
       # 엔진 설정 DB 저장
       await self._save_engine_settings(engine_name, designated_funds, leverage, funds_percent)
   ```

**✅ 사실**: 런타임에서 **GUI를 통해 레버리지 변경 가능**합니다.

---

### 3. 데이터베이스 저장 및 복원

#### DB 저장
```python
# backend/core/yona_service.py (Line 838-869)
async def _save_engine_settings(self, engine_name: str, designated_funds: float, 
                                applied_leverage: int, funds_percent: float):
    # engine_settings 테이블에 저장
    await db.execute("""
        UPDATE engine_settings 
        SET designated_funds = ?, applied_leverage = ?, 
            funds_percent = ?, updated_at_utc = ?
        WHERE engine_name = ?
    """, (designated_funds, applied_leverage, funds_percent, now_utc, engine_name))
```

#### DB 로드
```python
# backend/core/yona_service.py (Line 873-903)
async def _load_engine_settings(self):
    # DB에서 저장된 레버리지 로드
    for row in rows:
        engine_name = row["engine_name"]
        applied_leverage = row["applied_leverage"]
        
        # 레버리지 설정 (config 업데이트)
        engine_manager.engines[engine_name].config["leverage"] = applied_leverage
```

**✅ 사실**: 변경된 레버리지는 **DB에 저장**되어 다음 실행 시 **복원**됩니다.

---

## ⚠️ 발견된 문제점

### 1. GUI 슬라이더 초기값 불일치
| 엔진 | 코드 초기값 | GUI 슬라이더 초기값 | 문제 |
|------|------------|-------------------|------|
| Alpha | 5x | 1x | ❌ 불일치 |
| Beta | 3x | 1x | ❌ 불일치 |
| Gamma | 2x | 1x | ❌ 불일치 |

**문제점**:
- 엔진 초기화 시 코드에서는 5x/3x/2x로 설정
- GUI 슬라이더는 1x로 표시
- **사용자가 혼란**을 겪을 수 있음

### 2. 하드코딩된 초기값의 한계
```python
# 각 엔진 파일에 고정
Alpha: "leverage": 5
Beta:  "leverage": 3
Gamma: "leverage": 2
```

**문제점**:
- 초기값을 변경하려면 **코드 수정 필요**
- 설정 파일(`.env` 등)로 관리하지 않음
- 개발자가 아닌 사용자는 변경 불가

---

## 📋 레버리지 설정 흐름도

```
[앱 시작]
    ↓
[엔진 초기화]
    ├─ Alpha: leverage = 5 (하드코딩)
    ├─ Beta:  leverage = 3 (하드코딩)
    └─ Gamma: leverage = 2 (하드코딩)
    ↓
[DB에서 설정 로드]
    └─ 저장된 값이 있으면 → config["leverage"] 덮어쓰기
    └─ 없으면 → 하드코딩 값 유지
    ↓
[GUI 표시]
    └─ 슬라이더: 1x (고정)  ← ⚠️ 실제 값과 불일치!
    ↓
[사용자 조작]
    ├─ 슬라이더 이동 → 라벨 업데이트
    └─ Apply Settings 버튼 클릭
        ↓
    [바이낸스 API 호출]
        └─ set_leverage(symbol, leverage)
        ↓
    [백엔드 API 호출]
        └─ POST /api/v1/engine/leverage
        ↓
    [엔진 config 업데이트]
        └─ engine.update_config({"leverage": leverage})
        ↓
    [DB 저장]
        └─ engine_settings 테이블 UPDATE
```

---

## 🔧 레버리지 적용 메커니즘

### 실제 거래 시 레버리지 사용
```python
# alpha_strategy.py (Line 354)
leverage = self.config.get("leverage", 1)
quantity = (self.designated_funds * leverage) / self.current_price
```

### 바이낸스 API 레버리지 설정
```python
# binance_client.py (Line 247-272)
def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
    # POST /fapi/v1/leverage
    params = {
        "symbol": symbol,
        "leverage": leverage
    }
    return self._send_signed_request("POST", "/fapi/v1/leverage", params=params)
```

**✅ 확인**: 실제 거래 시 `config["leverage"]` 값을 사용하여 주문 수량 계산

---

## 📝 최종 정리

### 하드코딩된 부분
1. ✅ **초기 레버리지 값**: 각 엔진 코드에 고정
   - Alpha: 5x
   - Beta: 3x
   - Gamma: 2x

2. ✅ **GUI 슬라이더 초기값**: 1x (고정)

### 변경 가능한 부분
1. ✅ **런타임 변경**: GUI 슬라이더 + Apply Settings 버튼
2. ✅ **DB 저장**: `engine_settings` 테이블에 `applied_leverage` 저장
3. ✅ **자동 복원**: 다음 실행 시 DB에서 로드하여 적용

### 레버리지 적용 우선순위
```
1. DB 저장값 (있는 경우)
   ↓ 없으면
2. 하드코딩 초기값 (Alpha 5x, Beta 3x, Gamma 2x)
```

---

## ⚠️ 권고사항

### 1. GUI 초기값 동기화
- GUI 슬라이더를 엔진의 실제 레버리지 값으로 초기화
- 또는 DB에서 로드한 값으로 설정

### 2. 설정 파일로 관리
```env
# .env 파일에 추가 (예시)
ALPHA_DEFAULT_LEVERAGE=5
BETA_DEFAULT_LEVERAGE=3
GAMMA_DEFAULT_LEVERAGE=2
```

### 3. 사용자 안내
- 현재 적용된 레버리지를 명확히 표시
- 슬라이더 값과 실제 적용 값의 차이 해소

---

**검증자**: GitHub Copilot  
**검증 완료 시각**: 2025-11-18 20:55:00 (KST)

# ALCHUSDT 심볼 준비 실패 오류 진단 보고서

**보고 일시**: 2025-11-20 18:41  
**오류 메시지**: `Failed to prepare ALCHUSDT (margin/leverage setup error)`  
**오류 발생 시각**: [18:37:51] (지속적 발생)  
**영향 범위**: ALCHUSDT 심볼 배정 시 거래 활성화 불가

---

## 1. 오류 재현 및 근본 원인 분석

### 1.1 실제 API 테스트 결과

#### ✅ ALCHUSDT 심볼 지원 여부 확인

```python
client.is_symbol_supported('ALCHUSDT')
```

**결과**: 
```json
{
  "supported": true,
  "reason": "OK",
  "filters": {
    "LOT_SIZE": {"minQty": "1", "stepSize": "1"},
    "MIN_NOTIONAL": {"notional": "5"},
    ...
  }
}
```

✅ **ALCHUSDT는 Binance Futures에 정상 등록되어 있음**

---

#### ❌ 마진 타입 설정 실패 (ISOLATED)

```python
client.set_margin_type('ALCHUSDT', isolated=True)
```

**결과**:
```json
{
  "error": "{\"code\":-4168,\"msg\":\"Unable to adjust to isolated-margin mode under the Multi-Assets mode.\"}",
  "code": 400
}
```

**Binance 오류 코드**: `-4168`  
**오류 메시지**: `Unable to adjust to isolated-margin mode under the Multi-Assets mode.`

🔴 **핵심 문제**: 사용자의 Binance 계정이 **Multi-Assets 모드**로 설정되어 있어 **ISOLATED 마진 타입 설정 불가능**

---

#### ✅ 레버리지 설정 성공

```python
client.set_leverage('ALCHUSDT', 50)
```

**결과**:
```json
{
  "symbol": "ALCHUSDT",
  "leverage": 50,
  "maxNotionalValue": "5000"
}
```

✅ **레버리지는 정상적으로 설정됨** (마진 타입 실패와 무관)

---

### 1.2 오류 발생 경로 추적

```
[GUI] 설정 적용 버튼 클릭
    ↓
[API] POST /api/v1/engine/prepare-symbol
    ↓
[routes.py:343] engine.orchestrator.exec.prepare_symbol()
    ↓
[execution_adapter.py:45] prepare_symbol(symbol, leverage, isolated)
    ↓
[execution_adapter.py:47] client.set_margin_type(symbol, isolated=True)
    ↓
[binance_client.py:331] POST /fapi/v1/marginType
    ↓
❌ Binance API 오류: -4168 (Multi-Assets 모드 충돌)
    ↓
[execution_adapter.py:49] if "error" in mt and not mt.get("alreadySet")
    ↓
[execution_adapter.py:50] logger.error() + return False
    ↓
[routes.py:350] if not ok: raise HTTPException(500)
    ↓
[GUI] ⚠️ Binance 설정 실패 표시
```

---

## 2. 근본 원인 상세 분석

### 2.1 Binance Multi-Assets Mode란?

**Multi-Assets Mode** (다중 자산 모드):
- Binance Futures 계정 설정 중 하나
- 활성화 시: 여러 자산(BTC, ETH, USDT 등)을 **공통 증거금**으로 사용
- 제약 사항: **ISOLATED 마진 타입 사용 불가** (CROSSED만 가능)

**Single-Asset Mode** (단일 자산 모드):
- 기본 모드
- USDT만 증거금으로 사용
- ISOLATED / CROSSED 모두 사용 가능

### 2.2 현재 사용자 계정 상태

| 항목 | 상태 |
|------|------|
| 계정 모드 | **Multi-Assets Mode** |
| ISOLATED 마진 사용 가능 여부 | ❌ 불가능 |
| CROSSED 마진 사용 가능 여부 | ✅ 가능 |
| 앱 기본 설정 | `isolated_margin = True` |

**충돌**: 앱은 ISOLATED를 요구하지만, 계정은 Multi-Assets 모드로 ISOLATED 불가

---

### 2.3 코드 로직 분석

#### execution_adapter.py (현재 로직)

```python
def prepare_symbol(self, symbol: str, leverage: int, isolated: bool = True) -> bool:
    # 마진 타입 설정
    mt = self.client.set_margin_type(symbol, isolated=isolated)
    if "error" in mt and not mt.get("alreadySet"):
        logger.error(f"마진 타입 설정 실패: {mt}")
        return False  # ← 여기서 실패
    
    # 레버리지 설정
    lv = self.client.set_leverage(symbol, leverage)
    if "error" in lv:
        logger.error(f"레버리지 설정 실패: {lv}")
        return False
    return True
```

**문제점**:
1. `alreadySet` 필드는 `-4046` 오류 (이미 동일 마진 타입) 전용
2. `-4168` 오류 (Multi-Assets 모드 충돌)는 감지 못함
3. 모든 마진 타입 오류를 실패로 간주 → `return False`

---

#### binance_client.py (마진 타입 설정)

```python
def set_margin_type(self, symbol: str, isolated: bool = True) -> Dict[str, Any]:
    params = {
        "symbol": symbol,
        "marginType": "ISOLATED" if isolated else "CROSSED",
    }
    resp = self._send_signed_request("POST", "/fapi/v1/marginType", params=params, ...)
    
    # -4046 (이미 동일 마진) 처리
    if "error" in resp:
        try:
            data = json.loads(resp.get("error", "{}"))
            code = data.get("code")
            if code == -4046 or "No need to change margin type" in msg:
                return {"symbol": symbol, "marginType": "...", "alreadySet": True}
        except Exception:
            pass
    return resp  # ← -4168 오류 그대로 반환
```

**문제점**:
- `-4168` (Multi-Assets 모드) 오류는 별도 처리 없음
- 에러 응답 그대로 반환 → `execution_adapter`에서 실패 판정

---

## 3. 오류 영향 범위

### 3.1 발생 조건

| 조건 | 상태 |
|------|------|
| Binance 계정이 Multi-Assets 모드 | ✅ 해당 |
| 앱 설정이 `isolated_margin = True` | ✅ 해당 |
| 심볼 배정 후 "설정 적용" 버튼 클릭 | ✅ 해당 |

→ **ALCHUSDT 뿐만 아니라 모든 심볼에서 동일 오류 발생 가능**

### 3.2 영향받는 기능

| 기능 | 상태 | 설명 |
|------|------|------|
| 심볼 배정 | ✅ 정상 | DB 저장만 수행 |
| 설정 적용 (prepare-symbol) | ❌ 실패 | 마진 타입 설정 불가 |
| 거래 활성화 | ⚠️ 불명확 | 마진 타입 미설정 시 거동 확인 필요 |
| 실제 주문 실행 | ⚠️ 리스크 | CROSSED 모드로 작동 가능 (의도와 다름) |

### 3.3 잠재적 리스크

1. **마진 타입 불일치**
   - 앱은 ISOLATED를 가정하지만, 실제는 CROSSED로 작동
   - CROSSED: 모든 포지션이 증거금 공유 → 한 포지션 청산 시 다른 포지션 영향

2. **거래 활성화 실패**
   - `prepare_symbol()` 실패 시 HTTP 500 오류
   - GUI에 "Binance 설정 실패" 표시
   - 사용자는 거래를 시작할 수 없음

3. **데이터 불일치**
   - DB에는 심볼 저장되지만 Binance 설정은 실패
   - 재시도 시 반복 오류 발생

---

## 4. 현재 코드 동작 검증

### 4.1 prepare_symbol() 함수 흐름

```
입력: symbol="ALCHUSDT", leverage=50, isolated=True

1. set_margin_type("ALCHUSDT", isolated=True)
   → Binance API: POST /fapi/v1/marginType
   → 응답: {"error": "...-4168...", "code": 400}

2. if "error" in mt and not mt.get("alreadySet"):
   → "error" in mt: True
   → mt.get("alreadySet"): None (False)
   → 조건 충족: True

3. logger.error(f"마진 타입 설정 실패: {mt}")
   → 로그: "마진 타입 설정 실패: {'error': '...', 'code': 400}"

4. return False
   → 함수 종료 (레버리지 설정 시도 안함)
```

**결과**: `prepare_symbol()` 반환값 = `False`

---

### 4.2 routes.py 엔드포인트 동작

```python
ok = engine.orchestrator.exec.prepare_symbol(
    request.symbol, 
    request.leverage, 
    engine.orchestrator.cfg.isolated_margin
)

if ok:
    return {"status": "success", ...}
else:
    # ← 여기로 진입
    raise HTTPException(
        status_code=500, 
        detail=f"Failed to prepare {request.symbol} (margin/leverage setup error)"
    )
```

**결과**: HTTP 500 오류 반환 → GUI에 "⚠️ Binance 설정 실패" 표시

---

## 5. 해결 방안

### 5.1 근본 해결책 (권장)

#### 방안 A: 사용자 계정 설정 변경

**조치**: Binance 계정을 **Multi-Assets 모드 → Single-Asset 모드**로 변경

**절차**:
1. Binance Futures 웹/앱 접속
2. 계정 설정 → Assets Mode
3. "Multi-Assets Mode" 비활성화
4. "Single-Asset Mode" 활성화
5. 앱에서 재시도

**장점**:
- ✅ 코드 수정 불필요
- ✅ ISOLATED 마진 완전 지원
- ✅ 앱 설계 의도대로 작동

**단점**:
- ❌ 사용자 수동 작업 필요
- ❌ Multi-Assets 모드 장점 포기 (다중 자산 증거금)

---

#### 방안 B: 앱에서 CROSSED 모드 지원 추가

**조치**: Multi-Assets 계정 자동 감지 및 CROSSED 모드로 폴백

**구현 위치**: `execution_adapter.py`

**로직**:
```python
def prepare_symbol(self, symbol: str, leverage: int, isolated: bool = True) -> bool:
    # 1. ISOLATED 시도
    mt = self.client.set_margin_type(symbol, isolated=True)
    
    # 2. -4168 오류 시 CROSSED로 폴백
    if "error" in mt:
        try:
            data = json.loads(mt.get("error", "{}"))
            code = data.get("code")
            
            # -4168: Multi-Assets 모드 → CROSSED로 재시도
            if code == -4168:
                logger.warning(f"Multi-Assets 모드 감지: {symbol} → CROSSED 마진으로 설정")
                mt = self.client.set_margin_type(symbol, isolated=False)
                
                if "error" in mt and not mt.get("alreadySet"):
                    logger.error(f"CROSSED 마진 설정도 실패: {mt}")
                    return False
            
            # -4046: 이미 동일 마진 (정상)
            elif code == -4046 or mt.get("alreadySet"):
                pass
            
            else:
                logger.error(f"마진 타입 설정 실패: {mt}")
                return False
        except Exception as e:
            logger.error(f"마진 타입 오류 처리 중 예외: {e}")
            return False
    
    # 3. 레버리지 설정
    lv = self.client.set_leverage(symbol, leverage)
    if "error" in lv:
        logger.error(f"레버리지 설정 실패: {lv}")
        return False
    
    return True
```

**장점**:
- ✅ 사용자 작업 불필요
- ✅ Multi-Assets / Single-Asset 계정 모두 지원
- ✅ 자동 폴백으로 안정성 향상

**단점**:
- ⚠️ CROSSED 모드는 모든 포지션이 증거금 공유 (리스크 증가)
- ⚠️ 사용자가 마진 모드를 인지 못할 수 있음

---

### 5.2 임시 해결책

#### 방안 C: -4168 오류 무시 (비권장)

**조치**: `-4168` 오류를 정상으로 간주하고 진행

```python
if "error" in mt:
    data = json.loads(mt.get("error", "{}"))
    code = data.get("code")
    
    # -4046, -4168 모두 정상으로 간주
    if code in [-4046, -4168] or mt.get("alreadySet"):
        logger.info(f"마진 타입 설정 스킵: {symbol} (code={code})")
    else:
        return False
```

**장점**:
- ✅ 간단한 수정
- ✅ 즉시 적용 가능

**단점**:
- ❌ 마진 타입 불일치 (ISOLATED 의도 ≠ CROSSED 실제)
- ❌ 리스크 관리 로직 오작동 가능
- ❌ 의도하지 않은 청산 위험

---

### 5.3 추가 개선 사항

#### GUI 개선: 마진 모드 표시

**목적**: 사용자에게 현재 마진 모드 알림

**구현**:
1. `prepare-symbol` API 응답에 실제 적용된 마진 모드 포함
   ```json
   {
     "status": "success",
     "marginType": "CROSSED",  // 또는 "ISOLATED"
     "message": "⚠️ Multi-Assets 계정으로 CROSSED 마진 적용됨"
   }
   ```

2. GUI에 경고 메시지 표시
   ```
   [경고] CROSSED 마진 모드로 설정되었습니다.
   모든 포지션이 증거금을 공유합니다.
   ISOLATED 모드를 사용하려면 Binance 계정 설정을 변경하세요.
   ```

---

## 6. 권장 조치 사항

### 6.1 즉시 조치 (사용자)

**Priority 1**: Binance 계정 설정 확인 및 변경

1. **Binance Futures 웹 접속**
   - https://www.binance.com/en/futures

2. **Assets Mode 확인**
   - 계정 설정 → Portfolio → Assets Mode
   - 현재: "Multi-Assets Mode" (추정)

3. **Single-Asset Mode로 변경**
   - "Switch to Single-Asset Mode" 클릭
   - 확인 및 저장

4. **앱에서 재시도**
   - ALCHUSDT 심볼 배정
   - "설정 적용" 버튼 클릭
   - 정상 작동 확인

---

### 6.2 코드 개선 (개발자)

**Priority 2**: Multi-Assets 모드 자동 대응 로직 추가

**파일**: `backend/core/new_strategy/execution_adapter.py`

**개선 내용**:
1. `-4168` 오류 감지 시 CROSSED 모드로 폴백
2. 실제 적용된 마진 모드 로깅
3. API 응답에 마진 모드 정보 포함

**예상 효과**:
- Multi-Assets / Single-Asset 계정 모두 지원
- 사용자 수동 작업 불필요
- 오류 메시지 개선

---

### 6.3 GUI 개선 (개발자)

**Priority 3**: 마진 모드 표시 및 경고

**파일**: `gui/widgets/footer_engines_widget.py`

**개선 내용**:
1. `prepare-symbol` API 응답에서 마진 모드 파싱
2. CROSSED 모드 적용 시 경고 다이얼로그 표시
3. 엔진 상태에 마진 모드 표시 (ISOLATED/CROSSED)

**예상 효과**:
- 사용자 인지도 향상
- 의도하지 않은 리스크 방지

---

## 7. 테스트 시나리오

### 7.1 방안 A (사용자 계정 변경) 테스트

```
1. Binance 계정을 Single-Asset Mode로 변경
2. 앱 실행
3. ALCHUSDT 심볼 배정
4. "설정 적용" 클릭
5. 예상 결과:
   - ✅ "심볼 준비 완료" 메시지
   - ✅ ISOLATED 마진 적용
   - ✅ 레버리지 50배 적용
```

### 7.2 방안 B (코드 수정) 테스트

```
1. execution_adapter.py 수정 적용
2. 앱 재시작
3. ALCHUSDT 심볼 배정
4. "설정 적용" 클릭
5. 예상 결과:
   - ✅ "심볼 준비 완료 (CROSSED 마진)" 메시지
   - ⚠️ CROSSED 마진 적용 경고
   - ✅ 레버리지 50배 적용
```

---

## 8. 종합 결론

### 8.1 오류 원인 요약

```
근본 원인: Binance 계정 Multi-Assets 모드와 앱 ISOLATED 마진 설정 충돌

오류 코드: -4168
오류 메시지: "Unable to adjust to isolated-margin mode under the Multi-Assets mode."
발생 위치: execution_adapter.prepare_symbol() → binance_client.set_margin_type()
영향 범위: 모든 심볼의 "설정 적용" 기능
```

### 8.2 즉시 가능한 해결책

| 방안 | 구현 난이도 | 사용자 편의성 | 리스크 | 권장도 |
|------|-------------|---------------|--------|--------|
| A) 계정 변경 | ⭐☆☆☆☆ | ⭐⭐☆☆☆ | 낮음 | ⭐⭐⭐⭐⭐ |
| B) CROSSED 폴백 | ⭐⭐⭐☆☆ | ⭐⭐⭐⭐⭐ | 중간 | ⭐⭐⭐⭐☆ |
| C) 오류 무시 | ⭐☆☆☆☆ | ⭐⭐⭐☆☆ | 높음 | ⭐☆☆☆☆ |

### 8.3 최종 권장 사항

**단기 (즉시 실행)**:
1. ✅ **사용자에게 Binance 계정 Single-Asset Mode 변경 요청**
2. ✅ 변경 후 앱 재시도로 정상 작동 확인

**중기 (코드 개선)**:
1. ⭐ **execution_adapter.py에 -4168 오류 처리 추가** (방안 B)
2. ⭐ **GUI에 마진 모드 표시 및 경고 추가**
3. ⭐ **API 응답에 실제 마진 모드 정보 포함**

**장기 (기능 확장)**:
1. 💡 설정 UI에 마진 모드 선택 옵션 추가 (ISOLATED/CROSSED)
2. 💡 Multi-Assets 모드 자동 감지 및 권장 설정 제안
3. 💡 마진 모드별 리스크 설명 제공

---

## 9. 추가 확인 사항

### 9.1 다른 심볼에서도 동일 오류 발생 여부

**테스트 필요**:
- BTCUSDT
- ETHUSDT
- GRASSUSDT

**예상**: Multi-Assets 모드인 경우 **모든 심볼에서 동일 오류** 발생

### 9.2 기존 포지션 영향

**확인 사항**:
- 현재 열린 포지션의 마진 모드 확인
- 계정 변경 시 기존 포지션 영향 (Binance 문서 참조)

### 9.3 레버리지 설정 독립성

**검증 완료**: ✅ 레버리지는 마진 타입과 무관하게 정상 설정됨
- ALCHUSDT 50배 레버리지 설정 성공 확인

---

**보고서 작성**: 2025-11-20 18:41  
**테스트 환경**: Binance Futures Testnet/Mainnet  
**검증 방법**: 실제 API 호출 및 오류 코드 분석  
**신뢰도**: 높음 (Binance 공식 API 문서 기반)


# StrategyProfile 스키마 정의

**작성일:** 2025-11-18  
**목적:** Alpha/Beta/Gamma 전략 프로파일 구조 및 파라미터 정의  
**상태:** DRAFT → REVIEW → FROZEN

---

## 1. StrategyProfile 개요

### 1.1 목적
- 전략별 파라미터를 하나의 구조체로 관리
- JSON 직렬화/역직렬화 지원 (설정 파일 저장/로드)
- 런타임 파라미터 변경 및 검증
- 백테스트/실거래 동일 프로파일 사용

### 1.2 설계 원칙
- 불변성(Immutability): 생성 후 수정은 copy-on-write
- 검증(Validation): 모든 파라미터 범위 검증
- 타입 안전성: dataclass + 타입 힌트

---

## 2. StrategyProfile 클래스 정의

### 2.1 Python 클래스
```python
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from enum import Enum
import json

class StrategyMode(Enum):
    """전략 모드"""
    SCALPING = "scalping"  # 초단기 스캘핑
    DAY_TRADING = "day_trading"  # 단기 데이 트레이딩
    SWING = "swing"  # 스윙 트레이딩

class SignalMode(Enum):
    """신호 생성 모드"""
    SCORE_BASED = "score_based"  # 점수 시스템 (170점 만점)
    RULE_BASED = "rule_based"  # 규칙 기반 (AND/OR)

@dataclass
class StrategyProfile:
    """전략 프로파일"""
    
    # ========== 기본 정보 ==========
    name: str  # 프로파일 이름 (예: "Alpha", "Beta", "Gamma")
    description: str  # 설명
    mode: StrategyMode  # 전략 모드
    version: str = "1.0.0"  # 버전
    
    # ========== 타임프레임 ==========
    primary_interval: str = "1m"  # 주 타임프레임 (진입 신호)
    secondary_interval: str = "3m"  # 보조 타임프레임 (확인 신호)
    filter_interval: str = "15m"  # 필터 타임프레임 (큰 그림)
    
    # ========== 자금 관리 ==========
    initial_capital: float = 10000.0  # 초기 배분 자금 (USDT)
    risk_fraction: float = 0.01  # 거래당 위험 비율 (1% = 0.01)
    max_position_pct: float = 1.0  # 최대 포지션 크기 (자본 대비 100% = 1.0)
    
    # ========== 레버리지 ==========
    default_leverage: int = 1  # 기본 레버리지
    max_leverage: int = 50  # 최대 레버리지
    margin_type: str = "ISOLATED"  # "ISOLATED" or "CROSSED"
    
    # ========== 리스크 관리 ==========
    stop_loss_pct: float = 0.005  # 손절 (0.5%)
    take_profit_pct: float = 0.035  # 익절 (3.5%)
    trailing_stop_pct: float = 0.004  # 트레일링 (0.4%)
    trailing_activation_pct: float = 0.01  # 트레일링 활성화 수익률 (1%)
    breakeven_move_pct: float = 0.002  # 본절 이동 추가 이익 (0.2%)
    
    # ========== 시간 제한 ==========
    max_holding_time_sec: int = 1800  # 최대 보유 시간 (30분 = 1800초)
    max_daily_trades: int = 50  # 일일 최대 거래 횟수
    
    # ========== 신호 생성 ==========
    signal_mode: SignalMode = SignalMode.SCORE_BASED
    
    # 점수 시스템 가중치 (score_based 모드)
    score_weights: Dict[str, float] = field(default_factory=lambda: {
        "volume_spike": 30.0,
        "vwap_break": 20.0,
        "ema_alignment_15m": 20.0,
        "macd_cross": 15.0,
        "stoch_rebound_1m": 10.0,
        "ema_support_5m": 15.0,
        "trend_strength_15m": 10.0,
        "atr_stable": 10.0,
        # 감점
        "stoch_overbought": -10.0,
        "macd_divergence": -15.0
    })
    
    # 점수 임계값
    aggressive_entry_threshold: float = 160.0  # 즉시 진입 (94%)
    conservative_entry_threshold: float = 130.0  # 진입 권장 (76%)
    monitor_threshold: float = 100.0  # 모니터 상태 (59%)
    
    # 규칙 기반 조건 (rule_based 모드)
    entry_rules: Optional[List[str]] = None  # ["ema_alignment", "macd_cross", "volume_spike"]
    entry_logic: str = "AND"  # "AND" or "OR"
    
    # ========== 지표 설정 ==========
    ema_periods: List[int] = field(default_factory=lambda: [5, 10, 20, 60, 120])
    rsi_period: int = 14
    stoch_rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    volume_spike_threshold: float = 3.0  # 평균 대비 3배
    volume_lookback: int = 20
    
    # ========== 필터 조건 ==========
    enable_trend_filter: bool = True  # 15분봉 추세 필터
    min_trend_strength: str = "UPTREND"  # "UPTREND" or "STRONG_UPTREND"
    enable_volatility_filter: bool = True  # 변동성 필터
    max_atr_percentile: float = 90.0  # ATR 백분위 상한 (과열 방지)
    
    # ========== 계좌 수준 리스크 ==========
    max_daily_loss_pct: float = 0.02  # 일일 최대 손실 (2%)
    max_consecutive_losses: int = 3  # 최대 연속 손실
    max_drawdown_pct: float = 0.03  # 최대 드로우다운 (3%)
    
    # ========== 실행 옵션 ==========
    enable_compounding: bool = True  # 복리 재투자
    enable_partial_exit: bool = False  # 부분 청산 (미래 확장)
    partial_exit_pct: float = 0.5  # 부분 청산 비율 (50%)
    
    # ========== 로깅/모니터링 ==========
    log_level: str = "INFO"  # "DEBUG", "INFO", "WARNING", "ERROR"
    log_trades: bool = True
    log_signals: bool = False  # 미체결 신호도 로그
    
    def validate(self) -> bool:
        """
        프로파일 유효성 검증
        
        Returns:
            유효성 여부
            
        Raises:
            ValueError: 잘못된 파라미터
        """
        # 범위 검증
        if not (0.0 < self.risk_fraction <= 0.05):
            raise ValueError(f"risk_fraction must be in (0, 0.05], got {self.risk_fraction}")
        
        if not (1 <= self.default_leverage <= self.max_leverage):
            raise ValueError(f"default_leverage must be in [1, {self.max_leverage}]")
        
        if not (0.0 < self.stop_loss_pct < 0.1):
            raise ValueError(f"stop_loss_pct must be in (0, 0.1), got {self.stop_loss_pct}")
        
        if not (0.0 < self.take_profit_pct < 1.0):
            raise ValueError(f"take_profit_pct must be in (0, 1.0), got {self.take_profit_pct}")
        
        if self.take_profit_pct <= self.stop_loss_pct:
            raise ValueError("take_profit_pct must be > stop_loss_pct")
        
        if not (0.0 < self.trailing_stop_pct < self.take_profit_pct):
            raise ValueError("trailing_stop_pct must be in (0, take_profit_pct)")
        
        # 신호 모드 검증
        if self.signal_mode == SignalMode.SCORE_BASED:
            if not self.score_weights:
                raise ValueError("score_weights required for score_based mode")
        elif self.signal_mode == SignalMode.RULE_BASED:
            if not self.entry_rules:
                raise ValueError("entry_rules required for rule_based mode")
        
        return True
    
    def to_dict(self) -> Dict:
        """Dict로 변환 (JSON 직렬화용)"""
        data = asdict(self)
        # Enum을 문자열로 변환
        data['mode'] = self.mode.value
        data['signal_mode'] = self.signal_mode.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyProfile':
        """Dict에서 생성 (JSON 역직렬화용)"""
        # Enum 복원
        data['mode'] = StrategyMode(data['mode'])
        data['signal_mode'] = SignalMode(data['signal_mode'])
        return cls(**data)
    
    def to_json(self, file_path: str) -> None:
        """JSON 파일로 저장"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, file_path: str) -> 'StrategyProfile':
        """JSON 파일에서 로드"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def copy(self, **changes) -> 'StrategyProfile':
        """
        복사본 생성 (일부 파라미터 변경)
        
        Example:
            new_profile = profile.copy(take_profit_pct=0.04, leverage=10)
        """
        data = self.to_dict()
        data.update(changes)
        return self.from_dict(data)
```

---

## 3. 프로파일 정의 (Alpha/Beta/Gamma)

### 3.1 Alpha 프로파일 (초단기 스캘핑)
```python
ALPHA_PROFILE = StrategyProfile(
    name="Alpha",
    description="초단기 스캘핑 전략 (1분/3분봉 진입)",
    mode=StrategyMode.SCALPING,
    
    # 타임프레임
    primary_interval="1m",
    secondary_interval="3m",
    filter_interval="15m",
    
    # 자금
    initial_capital=10000.0,
    risk_fraction=0.01,  # 1%
    
    # 레버리지
    default_leverage=1,
    max_leverage=50,
    
    # 리스크
    stop_loss_pct=0.005,  # 0.5%
    take_profit_pct=0.035,  # 3.5%
    trailing_stop_pct=0.004,  # 0.4%
    trailing_activation_pct=0.01,  # 1%
    breakeven_move_pct=0.002,  # 0.2%
    
    # 시간
    max_holding_time_sec=1800,  # 30분
    max_daily_trades=50,
    
    # 신호
    signal_mode=SignalMode.SCORE_BASED,
    aggressive_entry_threshold=160.0,
    conservative_entry_threshold=130.0,
    
    # 필터
    enable_trend_filter=True,
    min_trend_strength="UPTREND",
    enable_volatility_filter=True,
    max_atr_percentile=90.0,
    
    # 계좌 리스크
    max_daily_loss_pct=0.02,
    max_consecutive_losses=3,
    max_drawdown_pct=0.03
)
```

### 3.2 Beta 프로파일 (초단기 스캘핑 - Alpha와 동일)
```python
BETA_PROFILE = StrategyProfile(
    name="Beta",
    description="초단기 스캘핑 전략 (1분/3분봉 진입)",
    mode=StrategyMode.SCALPING,
    
    # Alpha와 동일 설정
    primary_interval="1m",
    secondary_interval="3m",
    filter_interval="15m",
    
    initial_capital=10000.0,
    risk_fraction=0.01,
    
    default_leverage=1,
    max_leverage=50,
    
    stop_loss_pct=0.005,
    take_profit_pct=0.035,
    trailing_stop_pct=0.004,
    trailing_activation_pct=0.01,
    breakeven_move_pct=0.002,
    
    max_holding_time_sec=1800,
    max_daily_trades=50,
    
    signal_mode=SignalMode.SCORE_BASED,
    aggressive_entry_threshold=160.0,
    conservative_entry_threshold=130.0,
    
    enable_trend_filter=True,
    min_trend_strength="UPTREND",
    enable_volatility_filter=True,
    
    max_daily_loss_pct=0.02,
    max_consecutive_losses=3,
    max_drawdown_pct=0.03
)
```

### 3.3 Gamma 프로파일 (초단기 스캘핑 - Alpha/Beta와 동일)
```python
GAMMA_PROFILE = StrategyProfile(
    name="Gamma",
    description="초단기 스캘핑 전략 (1분/3분봉 진입)",
    mode=StrategyMode.SCALPING,
    
    # Alpha/Beta와 동일 설정
    primary_interval="1m",
    secondary_interval="3m",
    filter_interval="15m",
    
    initial_capital=10000.0,
    risk_fraction=0.01,
    
    default_leverage=1,
    max_leverage=50,
    
    stop_loss_pct=0.005,
    take_profit_pct=0.035,
    trailing_stop_pct=0.004,
    trailing_activation_pct=0.01,
    breakeven_move_pct=0.002,
    
    max_holding_time_sec=1800,
    max_daily_trades=50,
    
    signal_mode=SignalMode.SCORE_BASED,
    aggressive_entry_threshold=160.0,
    conservative_entry_threshold=130.0,
    
    enable_trend_filter=True,
    min_trend_strength="UPTREND",
    enable_volatility_filter=True,
    
    max_daily_loss_pct=0.02,
    max_consecutive_losses=3,
    max_drawdown_pct=0.03
)
```

---

## 4. JSON 파일 형식

### 4.1 alpha_profile.json
```json
{
  "name": "Alpha",
  "description": "초단기 스캘핑 전략 (1분/3분봉 진입)",
  "mode": "scalping",
  "version": "1.0.0",
  
  "primary_interval": "1m",
  "secondary_interval": "3m",
  "filter_interval": "15m",
  
  "initial_capital": 10000.0,
  "risk_fraction": 0.01,
  "max_position_pct": 1.0,
  
  "default_leverage": 1,
  "max_leverage": 50,
  "margin_type": "ISOLATED",
  
  "stop_loss_pct": 0.005,
  "take_profit_pct": 0.035,
  "trailing_stop_pct": 0.004,
  "trailing_activation_pct": 0.01,
  "breakeven_move_pct": 0.002,
  
  "max_holding_time_sec": 1800,
  "max_daily_trades": 50,
  
  "signal_mode": "score_based",
  "score_weights": {
    "volume_spike": 30.0,
    "vwap_break": 20.0,
    "ema_alignment_15m": 20.0,
    "macd_cross": 15.0,
    "stoch_rebound_1m": 10.0,
    "ema_support_5m": 15.0,
    "trend_strength_15m": 10.0,
    "atr_stable": 10.0,
    "stoch_overbought": -10.0,
    "macd_divergence": -15.0
  },
  "aggressive_entry_threshold": 160.0,
  "conservative_entry_threshold": 130.0,
  "monitor_threshold": 100.0,
  
  "entry_rules": null,
  "entry_logic": "AND",
  
  "ema_periods": [5, 10, 20, 60, 120],
  "rsi_period": 14,
  "stoch_rsi_period": 14,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "atr_period": 14,
  "volume_spike_threshold": 3.0,
  "volume_lookback": 20,
  
  "enable_trend_filter": true,
  "min_trend_strength": "UPTREND",
  "enable_volatility_filter": true,
  "max_atr_percentile": 90.0,
  
  "max_daily_loss_pct": 0.02,
  "max_consecutive_losses": 3,
  "max_drawdown_pct": 0.03,
  
  "enable_compounding": true,
  "enable_partial_exit": false,
  "partial_exit_pct": 0.5,
  
  "log_level": "INFO",
  "log_trades": true,
  "log_signals": false
}
```

---

## 5. 프로파일 사용 예제

### 5.1 로드 및 검증
```python
# JSON에서 로드
profile = StrategyProfile.from_json("config/alpha_profile.json")

# 검증
profile.validate()

# 사용
print(f"전략: {profile.name}")
print(f"익절: {profile.take_profit_pct * 100}%")
print(f"손절: {profile.stop_loss_pct * 100}%")
```

### 5.2 런타임 수정
```python
# 복사본 생성 (레버리지 변경)
new_profile = profile.copy(default_leverage=10, max_leverage=50)

# 검증
new_profile.validate()

# 저장
new_profile.to_json("config/alpha_profile_leveraged.json")
```

### 5.3 프로파일 비교
```python
profiles = {
    "Alpha": StrategyProfile.from_json("config/alpha_profile.json"),
    "Beta": StrategyProfile.from_json("config/beta_profile.json"),
    "Gamma": StrategyProfile.from_json("config/gamma_profile.json")
}

for name, p in profiles.items():
    print(f"{name}: TP={p.take_profit_pct*100}%, "
          f"SL={p.stop_loss_pct*100}%, "
          f"Max Hold={p.max_holding_time_sec}s")
```

---

## 6. 프로파일 관리 전략

### 6.1 파일 구조
```
config/
├── profiles/
│   ├── alpha_profile.json
│   ├── beta_profile.json
│   ├── gamma_profile.json
│   ├── alpha_aggressive.json (변형)
│   └── alpha_conservative.json (변형)
└── active_profiles.json (현재 활성 프로파일)
```

### 6.2 활성 프로파일 관리
```json
{
  "active_profiles": {
    "Alpha": "config/profiles/alpha_profile.json",
    "Beta": "config/profiles/beta_profile.json",
    "Gamma": "config/profiles/gamma_profile.json"
  },
  "last_updated": "2025-01-18T10:30:00Z"
}
```

### 6.3 버전 관리
- 프로파일 변경 시 `version` 필드 업데이트
- 이전 버전 백업 (`alpha_profile_v1.0.0.json.bak`)
- Git으로 변경 이력 추적

---

## 7. 프로파일 최적화 워크플로우

### 7.1 백테스트 기반 최적화
```python
# 1. 기본 프로파일 로드
base_profile = StrategyProfile.from_json("config/alpha_profile.json")

# 2. 파라미터 범위 정의
param_ranges = {
    "take_profit_pct": [0.03, 0.035, 0.04, 0.045],
    "stop_loss_pct": [0.005, 0.0075, 0.01],
    "trailing_stop_pct": [0.003, 0.004, 0.005]
}

# 3. 백테스트 실행
results = []
for tp in param_ranges["take_profit_pct"]:
    for sl in param_ranges["stop_loss_pct"]:
        for ts in param_ranges["trailing_stop_pct"]:
            test_profile = base_profile.copy(
                take_profit_pct=tp,
                stop_loss_pct=sl,
                trailing_stop_pct=ts
            )
            report = backtest_adapter.run(BacktestConfig(profile=test_profile, ...))
            results.append({
                "params": {"tp": tp, "sl": sl, "ts": ts},
                "sharpe": report.metrics.sharpe_ratio,
                "return": report.metrics.total_return_pct
            })

# 4. 최적 파라미터 선택
best = max(results, key=lambda x: x["sharpe"])
print(f"Best Sharpe: {best['sharpe']:.2f} with params {best['params']}")

# 5. 최적 프로파일 저장
optimized_profile = base_profile.copy(**best["params"])
optimized_profile.to_json("config/alpha_profile_optimized.json")
```

---

## 8. 검증 규칙

### 8.1 필수 검증
- `risk_fraction`: (0, 0.05]
- `default_leverage`: [1, max_leverage]
- `stop_loss_pct`: (0, 0.1)
- `take_profit_pct`: (0, 1.0) AND > stop_loss_pct
- `trailing_stop_pct`: (0, take_profit_pct)
- `max_daily_loss_pct`: (0, 0.1)
- `max_drawdown_pct`: (0, 0.2)

### 8.2 논리 검증
- `signal_mode == SCORE_BASED` → `score_weights` 필수
- `signal_mode == RULE_BASED` → `entry_rules` 필수
- `enable_trend_filter == True` → `filter_interval` 필수
- `enable_partial_exit == True` → `0 < partial_exit_pct < 1`

---

## 9. 마이그레이션 계획 (Legacy → New)

### 9.1 Legacy 설정 변환
```python
def convert_legacy_to_profile(legacy_config: Dict) -> StrategyProfile:
    """
    Legacy 엔진 설정을 StrategyProfile로 변환
    
    Args:
        legacy_config: {
            "capital_allocation": 100,
            "leverage": 5,
            "stop_loss_percent": 0.02,
            "take_profit_percent": 0.05,
            ...
        }
    """
    return StrategyProfile(
        name=legacy_config.get("engine_name", "Unknown"),
        description="Converted from legacy",
        mode=StrategyMode.SCALPING,
        
        initial_capital=legacy_config.get("capital_allocation", 100.0),
        default_leverage=legacy_config.get("leverage", 1),
        stop_loss_pct=legacy_config.get("stop_loss_percent", 0.005),
        take_profit_pct=legacy_config.get("take_profit_percent", 0.035),
        # ... 나머지 매핑
    )
```

---

## 10. 다음 단계

- [x] 모듈 인터페이스 설계 완료
- [x] 백테스트 하니스 계약 정의 완료
- [x] StrategyProfile 스키마 작성 완료
- [ ] 프로파일 JSON 파일 생성 (config/profiles/)
- [ ] 구현 시작 (DataFetcher → IndicatorEngine → ...)

---

**변경 이력:**
- 2025-11-18: 초안 작성 (Alpha/Beta/Gamma 프로파일 정의 완료, 모두 초단기 스캘핑 전략 통일)

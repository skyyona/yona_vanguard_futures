**백테스트 결과 필드(요약)**

- **run_id**: 고유 실행 ID (문자열)
- **strategy_name**: 전략 이름
- **symbol**: 심볼 (예: BTCUSDT)
- **interval**: 캔들 간격 (예: `1m`, `1h`)
- **start_time / end_time**: 밀리초 단위 UTC 타임스탬프
- **initial_balance**: 시뮬레이션 시작 자본
- **final_balance**: 시뮬레이션 종료 자본
- **profit_percentage**: 총 손익(퍼센트)
- **total_trades**: 체결된 트레이드 수
- **win_rate**: 승률(퍼센트)
- **parameters**: 실행에 사용된 파라미터 직렬화 문자열
- **created_at**: 레코드 생성 시각(밀리초 UTC)

**max_drawdown 관련 표준화 (중요)**

프로젝트 내에서 `max_drawdown` 필드와 `max_drawdown_pct` 라는 두 가지 명칭이 혼용되는 문제가 있었습니다. 표준화 방침은 다음과 같습니다:

- DB 스키마 및 저장소는 `max_drawdown` 칼럼을 유지합니다 (타입: Float).
- DB에 저장되는 `max_drawdown` 값은 **퍼센트(%)** 단위로 저장됩니다. 예: `12.34` = 12.34%.
- 시뮬레이터(`StrategySimulator`)는 내부 결과에서 `max_drawdown_pct`라는 키로 **퍼센트(%)** 값을 반환합니다.
- API 레이어(`BacktestService.get_backtest_result`)는 클라이언트 호환성과 명확성을 위해 DB에서 읽어올 때 `max_drawdown` 값을 그대로 노출하면서 추가로 `max_drawdown_pct` 키를 함께 포함시킵니다.

요약 표기:
- `max_drawdown` (DB 칼럼): 저장된 퍼센트 값
- `max_drawdown_pct` (시뮬레이터 결과 및 API 응답 보조 키): 동일한 퍼센트 값의 명확한 이름

이러한 매핑은 하위 호환성을 유지하면서, 외부 코드(특히 시뮬레이터/분석기)에서는 `max_drawdown_pct`를 사용하여 의미를 명확하게 표현할 수 있도록 합니다.

**권장 사용법**
- 외부 호출/API 응답을 소비하는 코드: `max_drawdown_pct` 우선 사용(존재하지 않으면 `max_drawdown` 사용).
- DB 직접 쿼리 코드를: `max_drawdown` 칼럼을 읽어 퍼센트로 해석.

문제가 있을 경우 이 문서를 업데이트하고, 필드명이 더 이상 혼용되지 않도록 호출부를 점검해 주세요.

**YONA Strategy Enhancement — Implementation & Validation Plan**

이 문서는 이미 구현된 기능(StrategyAnalyzer의 Volume Momentum, S/R 식별) 이후에 남아있는 작업과 검증·배포 절차를 정리합니다.

1) 남은 개발 항목
- 단위테스트 추가: 지표 수학 정확성, 룩어헤드 방지, SR 병합 동작 검증 (테스트 파일 추가됨)
- 백테스트 실행: 멀티코인·워크포워드·파라미터 스윕 (pilot 스크립트 추가됨)
- 통계적 검증: paired bootstrap 또는 block bootstrap으로 OOS 차이 검정
- 모니터링/로그: 신호의 reason code, 피처값, leverage 적용 이벤트 로깅

2) 검증 기준(요약)
- 주요 지표: Sharpe, MaxDrawdown, Profit Factor, Expectancy, WinRate
- 수용 조건(예시): OOS Sharpe >= baseline * 1.1 또는 false-entry 감소 >= 15% 및 MDD 악화 <= 10%

3) 실행 절차 (권장)
- 1단계: Pilot (3 심볼) — `scripts/backtest_skeleton.py`로 빠른 파라미터 확인
- 2단계: Full sweep (N 심볼, 워크포워드) — 병렬 배치, 결과 수집
- 3단계: 통계 검정 + 로버스트니스 리포트 생성

4) 리스크 및 완화책
- 룩어헤드: 모든 롤링 계산은 shift(1)로 처리
- 과최적화: 워크포워드, 다종목 일관성, 파라미터 단순화
- 조작성 거래: 볼륨 스파이크 시 캔들 방향/다중TF 필터 추가

5) 산출물
- 요약 테이블, 파라미터 히트맵, 코인별 리포트, 통계검정 결과, 권장 파라미터

6) 다음 단계 요청 포인트
- 대상 심볼, 기간, 리소스(병렬 수) 지시 필요 — 이후 전체 실행을 진행.

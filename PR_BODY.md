PR 요약 (붙여넣기용)

제목
fix(ui): StrategyAnalysisDialog 레이아웃 안전화 및 데이터 방어 패치

요약
- StrategyAnalysisDialog가 UI 재구성 시 발생하던 QLayout 경고와 간헐적 빈 화면 문제를 완화합니다.
- 백엔드 페이로드의 비정형(예: `executable_parameters`가 dict가 아닌 경우)에 대해 방어 로직을 추가하여 UI가 계속 동작하도록 보장합니다.

변경 요약
- `gui/widgets/strategy_analysis_dialog.py`
  - persistent `_base_layout` + `_replace_content_widget()` 도입으로 content widget을 원자적으로 교체
  - `executable_parameters`, `engine_results`, `risk_management` 등의 타입 검증 및 폴백
  - `_on_analysis_update()`에서 예외 로깅 추가(기존 swallow 제거)

테스트
- 자동: `python .\scripts\gui_investigate_dialog.py` (good/missing_exec/malformed/large/engine_only) — 모든 케이스 uncaught exception 없음
- 헤드리스: `python .\scripts\gui_assign_test.py` — assign flow 및 footer 적용 확인
- 수동: `python .\scripts\gui_manual_test.py` — 다이얼로그 직접 검증

검토 체크리스트 (간단)
- QLayout 경고 미발생
- malformed payload에서 UI가 중단되지 않음
- assign 신호가 footer에 정상 적용

참고
- 패치 아티팩트: `.git_patches/` (또는 `.\git_patches.zip`), `REVIEW_PATCHES.md`, `PR_DESCRIPTION.md`, `PR_CHECKLIST.md`


PR Body (English short version)

Title: fix(ui): StrategyAnalysisDialog layout-safety and defensive payload handling

Short: Introduces an atomic content-widget swap for StrategyAnalysisDialog to eliminate QLayout warnings and adds defensive type checks for backend payload fields to avoid UI failures on malformed data.

Files changed: `gui/widgets/strategy_analysis_dialog.py` (core), plus docs/patch artifacts in repo root.

Tests: run `scripts/gui_investigate_dialog.py`, `scripts/gui_assign_test.py`, and optionally `scripts/gui_manual_test.py` for manual validation.

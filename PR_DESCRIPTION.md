PR 제목: fix(ui): StrategyAnalysisDialog 레이아웃 안전화 및 데이터 방어 패치

요약
- `StrategyAnalysisDialog`의 UI 재구성 시 발생하던 QLayout 경고 및 간헐적 빈 화면(black/blank) 문제를 완화하기 위해 다이얼로그에 "atomic content widget swap" 패턴을 도입했습니다.
- 백엔드로부터 올 수 있는 비정형/비정상 페이로드(예: `executable_parameters`가 dict가 아닌 경우)에 대해 방어 로직을 추가하여 예외를 기록하고 안전하게 폴백합니다.

변경 사항 (주요)
- `gui/widgets/strategy_analysis_dialog.py`
  - 다이얼로그에 영구 `_base_layout`를 만들고, 전체 UI를 `content_widget`에 구성한 뒤 한 번에 교체하도록 `_replace_content_widget()` 추가.
  - `_init_ui()`에서 기존 `setLayout` 반복 호출을 피하도록 UI 빌드를 `content_widget`에서 수행 후 교체.
  - `engine_results`, `executable_parameters`, `risk_management` 등이 dict가 아닐 경우 `{}`로 강제하고 경고 로깅 추가(데이터 방어).
  - `_on_analysis_update()`에서 예외를 swallow하지 않고 로깅하여 내부 에러를 노출.
  - 레거시 헬퍼 `_create_engine_section`은 제거 상태로 명시(참고용으로 Git 히스토리에서 복원 가능).

동기
- QLayout 관련 경고는 UI의 레이아웃을 잘못 교체/삭제하는 패턴에서 발생합니다. 단순히 `setLayout`을 반복 호출하지 않고 content widget을 교체하면 경고와 화면 깜박임을 줄일 수 있습니다.
- 백엔드의 페이로드가 불완전하거나 형식이 다른 경우 UI 빌드 과정에서 예외가 발생하여 다이얼로그가 비어 보일 수 있으므로, 최소한의 방어를 통해 UI가 계속 동작하도록 보장해야 합니다.

테스트 수행 내역
- 비파괴 자동 진단: `python .\scripts\gui_investigate_dialog.py`
  - 케이스: `good`, `missing_exec`, `malformed`, `large`, `engine_only`, `local_capture`
  - 결과: 모든 케이스에서 uncaught exception 없음. `malformed` 케이스는 경고 로그 발생(강제 폴백).
  - 로그 위치: `logs/gui_investigate_dialog.log`

- 헤드리스 할당 테스트: `python .\scripts\gui_assign_test.py`
  - 백엔드 실패시 로컬 페이로드로 폴백, `engine_assigned` 신호 및 `footer` 업데이트 검증 완료.
  - 결과: 할당 플로우 정상 동작, Qt stylesheet 파싱 경고(비치명)만 출력.

- 인터랙티브 수동 검증: `python .\scripts\gui_manual_test.py`
  - 다이얼로그 직접 열어 버튼/스크롤/할당 흐름 확인(수동 닫기 전까지 유지).
  - QLayout 경고 미발생 확인.

리뷰 가이드
1. 변경 파일 확인
   - `gui/widgets/strategy_analysis_dialog.py` (핵심)
2. 로컬에서 패치 적용/확인
   - 패치 아티팩트: `.git_patches/` 및 `.git_patches/changes.bundle` (리뷰/적용 방법은 `REVIEW_PATCHES.md` 참고)
   - 권장 실행 순서:
     1. `git checkout -b review/layout-safety-apply`
     2. `git am .git_patches/*.patch` 또는 번들 사용
     3. `python .\scripts\gui_investigate_dialog.py`
     4. `python .\scripts\gui_assign_test.py`
     5. (선택) `python .\scripts\gui_manual_test.py`로 수동 확인
3. 중점 확인 항목
   - `QLayout` 경고 미발생 여부
   - malformed payload (예: 문자열 형태 `executable_parameters`)가 경고만 남기고 UI가 정상 동작하는지
   - `engine_assigned` 경로(footer 위젯 적용) 정상 동작 여부

롤백/병합 안내
- 롤백: 해당 브랜치를 리모트에 올린 뒤 PR 레벨에서 revert/rollback 권장. 로컬에서 복구하려면 `git checkout main`(또는 이전 정상 커밋) 후 `git reset --hard <commit>` 사용.
- 병합: 코드리뷰 통과 후 `fix/strategy-layout-safety-apply`를 `main`(또는 대상 브랜치)로 병합.

참고사항
- 레거시 제거 후보 함수 `_create_engine_section`은 현재 `NotImplementedError`로 남겨두었으므로, 완전 제거 전 반드시 QA를 권장합니다.
- 추가로 `gui/main.py`와 `gui/widgets/footer_engines_widget.py`의 호환성을 자동화하는 유닛 테스트(페이로드 변형 케이스)를 추가하면 회귀를 방지하는데 도움이 됩니다.

작성자: 자동 패치 생성기

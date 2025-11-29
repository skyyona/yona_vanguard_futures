PR 검토 체크리스트

- [ ] 코드 변경 파일 검토
  - `gui/widgets/strategy_analysis_dialog.py`의 변경점(레이아웃 교체 패턴, 데이터 방어 로직, 로깅) 확인
- [ ] 스타일/품질
  - [ ] 코드 포맷(PEP8 스타일) 간단 확인
  - [ ] 불필요한 주석/디버그 코드 없음
- [ ] 동작 확인 (자동)
  - [ ] `python .\scripts\gui_investigate_dialog.py` 실행 — 모든 페이로드 케이스에서 uncaught exception 없음
  - [ ] `logs/gui_investigate_dialog.log` 에서 malformed 케이스 경고 확인
  - [ ] `python .\scripts\gui_assign_test.py` 실행 — assign 신호와 footer 업데이트 정상 동작
- [ ] 동작 확인 (수동)
  - [ ] `python .\scripts\gui_manual_test.py`로 다이얼로그 직접 띄워 UI가 정상 표시되는지 확인
  - [ ] Assign 버튼 클릭 후 `engine_assigned` 로그/동작 확인
  - [ ] QLayout 관련 경고(콘솔) 미발생 확인
- [ ] 성능/안정성
  - [ ] 대용량 payload(예: `large` 케이스)에서 UI가 과도하게 느려지지 않는지 확인
  - [ ] 메모리/객체 누수 의심 (장시간 열어두기 테스트 권장)
- [ ] 보안/데이터
  - [ ] 로그에 민감 정보가 유출되지 않는지 확인
- [ ] 문서화
  - [ ] PR 본문(변경 내용, 테스트 경로, 롤백 방법) 적절히 설명되었는지 확인
- [ ] 병합 전 마지막 확인
  - [ ] CI(만약 존재한다면) 통과 여부 확인
  - [ ] 동료 리뷰어 1-2명 승인 획득

병합/롤백 명령 예시 (로컬)
- 리뷰 브랜치 생성 및 패치 적용
```powershell
git checkout -b review/layout-safety-apply
git am .git_patches/*.patch
```
- 번들에서 브랜치 복원
```powershell
mkdir tmp_repo_clone; cd tmp_repo_clone
git init
git bundle unbundle ../.git_patches/changes.bundle
git branch -r
# fetch into existing repo example
# git fetch ../.git_patches/changes.bundle refs/heads/*:refs/remotes/bundle/*
```
- 롤백(간단 예시)
```powershell
# main이 대상이라면
git checkout main
git reset --hard <commit-before-change>
```

검토자 메모: 레이아웃 안전화는 UI 안정성과 관련된 민감 변경이므로, 병합 후 스테이징에서 충분한 사용성 테스트를 권장합니다.

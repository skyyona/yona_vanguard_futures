# YONA Vanguard Futures (new) - 중단 세션 구현 완료

## 🎯 구현 완료 사항

### ✅ 1. 레이아웃 구조 (Binance Live vs1과 동일)

```
┌─────────────────────────────────────────────────────────┐
│                    Header Widget                        │ 60px
│  타이틀 | 계좌 정보 | 글로벌 세션 | START/STOP          │
├──────────────────────┬──────────────────────────────────┤
│  1열 (좌측 63%)      │  2열 (우측 37%)                  │
│                      │                                  │
│  ┌─────────────────┐ │  ┌────────────────────────────┐ │
│  │  탭 위젯        │ │  │  추세 분석 (120px)          │ │
│  │  ┌────────────┐ │ │  └────────────────────────────┘ │
│  │  │탭1: 랭킹   │ │ │  ┌────────────────────────────┐ │
│  │  │  - 급등예상 │ │ │  │  게이지 (120px)             │ │
│  │  │  - 랭킹표  │ │ │  └────────────────────────────┘ │
│  │  └────────────┘ │ │  ┌────────────────────────────┐ │
│  │  ┌────────────┐ │ │  │  타이밍 분석 차트 (확장)    │ │
│  │  │탭2: 블랙   │ │ │  │                             │ │
│  │  │  - SETTLING│ │ │  └────────────────────────────┘ │
│  │  │  - 블랙리스트│ │                                  │
│  │  └────────────┘ │ │                                  │
│  └─────────────────┘ │                                  │
├──────────────────────┴──────────────────────────────────┤
│                    Footer Widget                        │ 240px
│  상승에너지 | 거래 실행 | 리스크 관리                    │
└─────────────────────────────────────────────────────────┘
```

### ✅ 2. 구현된 위젯

#### 1열 - 탭 1: "금일 최고 && 실시간 랭킹"
- **SurgePredictionWidget**: 급등 예상 코인
  - 심볼 버튼 (클릭 시 바이낸스 페이지 + 포지션 분석)
  - 현재/예상 상승률 표시
  - 거래대금 표시
  - 거래량 증가 게이지 바
  - 신규상장/거래량급증/연속양봉 라벨

- **RankingTableWidget**: 실시간 랭킹리스트
  - 6개 컬럼: [선택, 랭크, 코인심볼, 상승률%, 누적, 상승유형]
  - 체크박스 선택 기능
  - 심볼 클릭 → 바이낸스 페이지 열기
  - 상승률/누적/유형 클릭 → 포지션 분석 시작
  - 신규상장/강세 신호 시 깜빡임 효과
  - [추가] 버튼으로 블랙리스트 등록

#### 1열 - 탭 2: "SETTLING update && BLACK list"
- **SettlingTableWidget**: SETTLING 테이블 (상단 30%)
  - 4개 컬럼: [선택, 코인심볼, 상승률%, 거래상태]
  - SETTLING 상태 코인 실시간 표시
  - 심볼 클릭 → 바이낸스 페이지 열기
  - [추가] 버튼으로 블랙리스트 등록

- **BlacklistTableWidget**: 블랙리스트 (하단 70%)
  - 4개 컬럼: [선택, 추가일시(UTC), 거래상태, 심볼]
  - MANUAL/SETTLING 상태 구분 표시
  - [해지] 버튼으로 블랙리스트 제거
  - 탭 전환 시 자동 로딩

#### 2열 - 포지션 진입 분석
- **TrendAnalysisWidget**: 추세 분석 (120px 고정)
  - 5분봉: 방향, 상태, 상승에너지 %, 강도 게이지
  - 15분봉: 방향, 상태, 상승에너지 %, 강도 게이지
  - 종합 판단: 강상승/상승/횡보/하락/강하락 + 거래 권장/금지

- **GaugeWidget**: 게이지 (120px 고정)
  - 0-100 점수 표시 (애니메이션 효과)
  - BPR (매수압력비율) 표시
  - VSS (거래량 강도) 표시
  - 색상: 0-40 빨강, 40-70 주황, 70-100 초록

- **TimingAnalysisView**: 타이밍 분석 차트 (확장)
  - Close 가격선 (검은색)
  - EMA20 (파랑), EMA50 (빨강)
  - VWAP (보라)
  - 진입 존 (초록 박스)
  - 손절 레벨 (빨강 선)
  - 익절1/익절2 레벨 (초록 선)

#### Footer - 기존 중단 세션 위젯 유지
- **MiddleSessionWidget**:
  - 상승에너지 강도 분석
  - 거래 포지션 진입/익절 분석
  - 거래 리스크 관리

### ✅ 3. 백엔드 연동

#### WebSocket 메시지 타입
- `BINANCE_LIVE_RANKING`: 실시간 랭킹 업데이트
- `RANKING_UPDATE`: 랭킹 테이블 갱신
- `SURGE_PREDICTION_UPDATE`: 급등 예상 코인 업데이트
- `SETTLING_UPDATE`: SETTLING 테이블 업데이트
- `TIMING_ANALYSIS_UPDATE`: 타이밍 분석 결과
- `TREND_ANALYSIS_UPDATE`: 추세 분석 결과
- `GAUGE_UPDATE`: 게이지 점수 업데이트
- `CRITICAL_ERROR`: 치명적 오류

#### REST API 엔드포인트
```
POST /api/v1/start                          # 실시간 분석 시작
POST /api/v1/stop                           # 실시간 분석 중지
GET  /api/v1/live/ranking                   # 랭킹 데이터 조회
GET  /api/v1/live/blacklist                 # 블랙리스트 조회
POST /api/v1/live/blacklist/add             # 블랙리스트 추가
POST /api/v1/live/blacklist/remove          # 블랙리스트 제거
GET  /api/v1/live/analysis/entry?symbol=X   # 포지션 진입 분석
```

## 🚀 실행 방법

### 1. GUI만 테스트 (백엔드 없이)
```powershell
cd "c:\Users\User\new\YONA Vanguard Futures(new)"
python test_gui.py
```

### 2. 전체 시스템 실행 (백엔드 + GUI)
```powershell
# 터미널 1: 백엔드 실행
cd "c:\Users\User\new\YONA Vanguard Futures(new)"
python backend/app_main.py

# 터미널 2: GUI 실행
cd "c:\Users\User\new\YONA Vanguard Futures(new)"
python gui/main.py
```

## 📋 주요 기능

### 실시간 랭킹 분석
1. 코인 심볼 클릭 → 바이낸스 선물 페이지 열기
2. 상승률/누적/유형 클릭 → 포지션 진입 분석 시작
3. 체크박스 선택 + [추가] → 블랙리스트 등록

### 포지션 진입 분석
1. 심볼 선택 시 자동으로 5분/15분봉 추세 분석
2. 0-100 점수 게이지 실시간 업데이트
3. 가격 차트에 진입존/손절/익절 레벨 표시
4. [ 타이밍 분석 ] 버튼으로 자동 분석 ON/OFF

### 블랙리스트 관리
1. 탭 전환 시 자동으로 블랙리스트 로딩
2. SETTLING 상태와 MANUAL 상태 구분 표시
3. 체크박스 선택 + [해지] → 블랙리스트 제거

## ⚠️ 주의사항

### 백엔드 연결
- 백엔드 서버가 실행되지 않으면 WebSocket 연결 오류 발생
- 오류 발생 시 로그에 기록되며, GUI는 계속 동작
- 백엔드 API 미응답 시 기본 데이터로 표시

### 데이터 표시
- 백엔드 연결 전: "바이낸스 API 연결 중", "데이터수신중" 등 표시
- WebSocket 재연결: 자동으로 재시도
- API 타임아웃: 5초 (timeout=5)

## 📝 파일 구조

```
YONA Vanguard Futures(new)/
├── gui/
│   ├── main.py                          # 메인 GUI (2열 레이아웃)
│   ├── widgets/
│   │   ├── __init__.py                  # 위젯 패키지
│   │   ├── header_widget.py             # 헤더
│   │   ├── ranking_table_widget.py      # 실시간 랭킹리스트 ✨ 신규
│   │   ├── surge_prediction_widget.py   # 급등 예상 코인 ✨ 신규
│   │   ├── blacklist_widgets.py         # SETTLING + 블랙리스트 ✨ 신규
│   │   ├── position_analysis_widgets.py # 추세/게이지/차트 ✨ 신규
│   │   └── middle_session_widget.py     # 기존 중단 세션 (푸터로 이동)
│   └── styles/
│       └── qss.py                       # 스타일시트 ✨ 신규
├── utils/
│   └── ws_client.py                     # WebSocket 클라이언트
├── backend/
│   ├── app_main.py                      # 백엔드 메인
│   └── utils/
│       └── logger.py                    # 로거
└── test_gui.py                          # GUI 테스트 스크립트 ✨ 신규
```

## ✅ 검증 완료

- [x] 2열 레이아웃 (63:37 비율)
- [x] 1열 탭 구조 (랭킹/블랙리스트)
- [x] 실시간 랭킹리스트 테이블 (6컬럼)
- [x] 급등 예상 코인 위젯
- [x] SETTLING 테이블
- [x] 블랙리스트 테이블
- [x] 추세 분석 위젯 (5분/15분봉)
- [x] 게이지 위젯 (애니메이션)
- [x] 타이밍 분석 차트
- [x] WebSocket 메시지 처리
- [x] REST API 연동
- [x] 블랙리스트 추가/제거
- [x] 심볼 클릭 → 바이낸스 페이지
- [x] 심볼 선택 → 포지션 분석
- [x] 탭 전환 시 자동 로딩
- [x] 깜빡임 효과 (신규상장/강세)
- [x] 오류 처리 (백엔드 연결 실패)

## 🎉 완료!

YONA Vanguard Futures(new)의 중단 세션이 Binance Live vs1과 동일한 구조로 완전히 구현되었습니다!

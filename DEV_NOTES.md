# 🎰 Boracay Casino Developer Notes

> **Last Updated**: 2026-02-14
> **Status**: 트레일링 스탑 전략 구현 완료 (테스트 진행 중)

---

## 1. Project Overview
MEXC 거래소에서 소액(5.1 USDT)으로 48시간 주기의 자동 베팅을 수행하는 토이 프로젝트.

## 2. System Architecture
```
Boracay_Casino/
├── main.py                 # 진입점 (Bot 초기화, JobQueue 등록)
├── core/
│   ├── config.py           # 중앙 설정 (모드, 주기, 금액)
│   ├── scheduler_engine.py # 핵심 로직 (베팅, 청산, 쿨타임)
│   ├── state_manager.py    # 상태 저장 (casino_state.json)
│   └── scanner.py          # 종목 선정 (변동률+거래량 기반)
├── exchange/
│   └── mexc.py             # MEXC API 커넥터
├── utils/
│   ├── telegram_bot.py     # 텔레그램 봇 (버튼 UI, 상태 조회)
│   └── logger.py           # 로깅
├── docs/                   # 📚 문서 (체계적 분류)
│   ├── planning/           # 기획/스펙 문서 (todo, 마스터플랜)
│   ├── deploy/             # 배포 관련 (서버, 워크플로우)
│   └── changelog/          # 작업 일지 (날짜별: YYYY-MM-DD.md)
└── logs/                   # 로그 저장
```

## 3. How It Works
1. **정오(12:00)** — 스캐너가 후보 코인을 텔레그램에 제시
2. **3분 이내** — 사용자가 버튼으로 선택 (미선택 시 자동 랜덤)
3. **포지션 감시 (5분 주기)**
   - **손절**: 수익률 -25% 도달 시 즉시 매도
   - **트레일링 활성화**: 수익률 +25% 도달 시 최고가 추적 시작
   - **익절**: 최고가 대비 10% 하락 시 즉시 매도
4. **72시간 후** — 손절/익절 미발동 시 자동 청산, 다음 정오까지 휴식

## 4. Configuration

### 모드 전환 (`core/config.py`)
- `RUN_MODE = "live"` → 72시간 주기, 정오 시작
- `RUN_MODE = "test"` → 10분 주기, 다음 분 경계에서 시작
- `ENABLE_REAL_ORDERS = True` → 실제 MEXC 주문 실행

### 테스트용 임시 설정
- `TESTING_FIRST_TRADE_DELAY_MINUTES = 5` → 첫 거래를 봇 시작 5분 후로 오버라이드
- 테스트 완료 후 `None`으로 변경하면 원래 정오 시작으로 복원

### 종목 선정 기준
- 24시간 변동률: +15% ~ +40% (Fallback: +10% ~ +40%)
- 거래대금: $100만 이상 (Fallback: $50만)
- 모멘텀 스코어 상위 20개 중 최대 3개 후보

### 손절/익절 전략
- **손절(Stop Loss)**: -25% 도달 시 즉시 매도
- **트레일링 활성화**: +25% 도달 시 트레일링 스탑 시작
- **익절(Trailing Stop)**: 최고가 대비 10% 하락 시 매도
- **감시 주기**: 5분 (300초)

## 5. How to Run
```bash
source venv/bin/activate
python main.py
```

## 6. Telegram Commands
- **📊 상태**: 현재 베팅 현황, 수익률, 청산 예정 시간
- **💰 매도**: 진행 중인 게임 즉시 청산
- **❓ 도움말**: 사용법 안내

## 7. Documentation Structure
프로젝트 문서는 `docs/` 폴더에 용도별로 분류되어 있다.

### 문서 분류 규칙
```
docs/
├── planning/           # 기획 및 스펙 문서
│   ├── toto_*.md      # 구현 예정/진행 중인 작업 (todo 문서)
│   └── *.md           # 프로젝트 기획서, 마스터플랜 등
│
├── deploy/            # 배포 관련 문서
│   ├── SERVER_DEPLOY.md        # 서버 배포 가이드
│   └── ORIGINAL_ONLY_WORKFLOW.md  # 배포 워크플로우
│
└── changelog/         # 작업 일지
    └── YYYY-MM-DD.md  # 날짜별 작업 내역 (상세)
```

### 신규 문서 작성 시
- **새 기능 스펙**: `docs/planning/toto_NNN_feature_YYMMDD.md`
- **작업 일지**: `docs/changelog/YYYY-MM-DD.md`
- **배포 가이드**: `docs/deploy/`에 추가
- **메인 개발 문서**: 루트의 `DEV_NOTES.md` 업데이트

### 완료된 todo 문서
- 완료 표시만 하고 `docs/planning/`에 유지 (히스토리 보존)
- 파일명에 날짜가 있어 작업 순서 추적 가능

## 8. Changelog

### 2026-02-14 - 최종 주기 결정 (72h)
- **장기 백테스트 완료** (Binance, 13개월)
  - 48h: -11.30% (158거래)
  - 72h: -13.34% (97거래) ⭐ 선택
  - 96h: -0.71% (76거래)
- **72h 주기 선택 근거**
  - 수년간 생존 가능 (연 -10% 손실)
  - 3일마다 거래 (재미 + 학습)
  - 거래 비용 합리적
  - MEXC 잡코인으로 더 나을 것 예상
- **설정 변경**
  - `LIVE_CYCLE_HOURS = 72`
  - MEXC 운영 확정
- **문서 업데이트**
  - `docs/changelog/2026-02-14-longterm-backtest.md`
  - `docs/changelog/2026-02-14-final-decision.md`

### 2026-02-14 - 스캐너 모드 백테스트 구현 및 검증
- **스캐너 모드 추가** ⭐
  - 매 사이클마다 새로운 알트코인 선정
  - scanner.py 로직 동일하게 구현
  - 상위 20개 중 랜덤 선택
- **실행 결과**
  - 6h: +1.25% (10거래, 승률 70%)
  - 12h: +0.71% (5거래, 승률 40%, 트레일링 1회)
  - 24h: +1.95% (3거래, 승률 100%, 트레일링 2회) ⭐
- **트레일링 스탑 작동 확인** ✅
  - AIV/USDT: +20.9% 익절
  - CTC/USDT: +12.75% 익절
  - TAL/USDT: 익절
- **파일**
  - `tests/backtester.py` 개선 (+100 lines)
  - `run_backtest.py` 개선
  - `backtest_scanner_test.json`
- **문서**
  - `tests/README.md` 업데이트
  - `docs/changelog/2026-02-14-part4-scanner-mode.md`

### 2026-02-14 - 백테스트 실행 및 검증
- **백테스트 엔진 검증 완료**
  - BTC/USDT, ETH/USDT 테스트 성공
  - 48h/72h/96h 주기 비교 실행
  - JSON 결과 저장 확인
  - 실행 속도: 2000 캔들 ~6초
- **발견 사항**
  - MEXC API 데이터 제약: 최근 7일만 가능
  - 메이저 코인 변동성 부족 (손절/익절 미발동)
  - 실전 알트코인 테스트 필요
- **결과 파일**
  - `backtest_btc_48_72_96.json`
  - `backtest_eth_48_72_96.json`
  - `test_result.json` (6h/12h/24h)
- **문서화**
  - `docs/changelog/2026-02-14-part3-backtest-results.md`

### 2026-02-14 - 백테스트 엔진 구현
- **tests/backtester.py**: 핵심 백테스트 엔진 구현
  - `BacktestConfig`: 전략 설정 (실전 로직과 동일)
  - `Position`: 포지션 상태 관리 (트레일링 스탑 포함)
  - `Trade`: 거래 기록 및 PNL 계산
  - `BacktestEngine`: 시뮬레이션 실행 엔진
  - OHLCV 데이터 다운로드 (MEXC API)
  - High/Low 기준 손절/익절 체크
  - 거래 비용 0.3% 반영
  - 마이너스 잔고 허용
- **run_backtest.py**: CLI 실행 스크립트
  - 다중 주기 비교 (48h, 72h, 96h)
  - JSON 결과 저장
- **tests/README.md**: 백테스트 가이드 문서
- **tests/__init__.py**: 패키지 초기화

### 2026-02-14 - 트레일링 스탑 전략 구현
- **config.py**: 손절/익절 설정 추가
  - `STOP_LOSS_THRESHOLD = -25.0`
  - `TS_ACTIVATION_REWARD = 25.0`
  - `TS_CALLBACK_RATE = 10.0`
  - `CHECK_INTERVAL = 300` (5분)
- **state_manager.py**: 트레일링 상태 관리 추가
  - `trailing_stop` 필드 (is_active, peak_price)
  - `activate_trailing_stop()`, `update_peak_price()` 메서드
- **scheduler_engine.py**: 손절/익절 로직 구현
  - 5분마다 손절 체크 (-25%)
  - +25% 도달 시 트레일링 활성화
  - 최고가 추적 및 10% 하락 시 익절
- **main.py**: 체크 주기 1분 → 5분 변경, 부팅 알림에 전략 정보 추가

### 2026-02-13 - 코드 정리 및 안정화
- 전체 `print()` → `logger` 교체 (mexc.py, scanner.py, telegram_bot.py)
- scanner.py 미사용 `find_target()` 제거
- telegram_bot.py `status()` 시간 계산 중복 코드 헬퍼로 추출
- state_manager.py 기본 상태에 누락 키 추가, `entry_price` 0 방어
- scheduler_engine.py 쿨타임 비교를 문자열→datetime으로 변경
- 시작점검(preflight) 기능 전면 제거 (config, scheduler, telegram, main)
- 첫 거래 시작 시각 체크에 2초 여유 추가 (JobQueue 타이밍 오차 대응)
- 후보 코인 안내 메시지 개수 동적 표시
- 테스트 모드 분 경계 정렬 (10분이면 00/10/20/30... 에 실행)
- 테스트용 `TESTING_FIRST_TRADE_DELAY_MINUTES` 설정 추가

## 9. 남은 작업
- MEXC 충전 완료 대기
- 충전 후: `TESTING_FIRST_TRADE_DELAY_MINUTES = None`, 실운영 값 확인 후 Docker 빌드 → 서버 배포
- ~~백테스트 실행하여 최적 주기 검증 (48h vs 72h vs 96h)~~ ✅ 완료 (72h 선택)
- 실전 운영 시작 (72h 주기, MEXC)
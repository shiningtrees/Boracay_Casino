# 🎰 Boracay Casino Developer Notes

> **Last Updated**: 2026-02-13
> **Status**: MEXC 충전 대기 중 (코드 완성, 테스트 진행 중)

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
└── logs/                   # 로그 저장
```

## 3. How It Works
1. **정오(12:00)** — 스캐너가 후보 코인을 텔레그램에 제시
2. **3분 이내** — 사용자가 버튼으로 선택 (미선택 시 자동 랜덤)
3. **48시간 동안** — 텔레그램에서 상태 확인, 원하면 수동 매도
4. **48시간 후** — 자동 청산, 다음 정오까지 휴식

## 4. Configuration

### 모드 전환 (`core/config.py`)
- `RUN_MODE = "live"` → 48시간 주기, 정오 시작
- `RUN_MODE = "test"` → 10분 주기, 다음 분 경계에서 시작
- `ENABLE_REAL_ORDERS = True` → 실제 MEXC 주문 실행

### 테스트용 임시 설정
- `TESTING_FIRST_TRADE_DELAY_MINUTES = 5` → 첫 거래를 봇 시작 5분 후로 오버라이드
- 테스트 완료 후 `None`으로 변경하면 원래 정오 시작으로 복원

### 종목 선정 기준
- 24시간 변동률: +15% ~ +40% (Fallback: +10% ~ +40%)
- 거래대금: $100만 이상 (Fallback: $50만)
- 모멘텀 스코어 상위 20개 중 최대 3개 후보

## 5. How to Run
```bash
source venv/bin/activate
python main.py
```

## 6. Telegram Commands
- **📊 상태**: 현재 베팅 현황, 수익률, 청산 예정 시간
- **💰 매도**: 진행 중인 게임 즉시 청산
- **❓ 도움말**: 사용법 안내

## 7. 2026-02-13 작업 내역
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

## 8. 남은 작업
- MEXC 충전 완료 대기
- 충전 후: `TESTING_FIRST_TRADE_DELAY_MINUTES = None`, 실운영 값 확인 후 Docker 빌드 → 서버 배포

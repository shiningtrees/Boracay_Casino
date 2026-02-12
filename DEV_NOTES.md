# 🎰 Boracay Casino Developer Notes

> **Last Updated**: 2026-02-12
> **Current Phase**: POC (Proof of Concept) Completed
> **Next Phase**: Real Trading (Wait 72h withdrawal limit)

---

## 1. Project Overview
**Boracay Casino**는 MEXC 거래소에서 소액(5.1 USDT)으로 48시간 주기의 자동 베팅을 수행하는 토이 프로젝트입니다.
- **Trader(본진)**: 업비트 안정적 매매 (별도 봇)
- **Casino(이곳)**: MEXC 공격적/재미용 매매 (별도 봇, 별도 토큰 사용)

## 2. System Architecture
```
Boracay_Casino/
├── main.py                 # 진입점 (Bot 초기화, JobQueue 등록)
├── core/
│   ├── config.py           # 중앙 설정 (주기, 금액 등)
│   ├── scheduler_engine.py # 핵심 로직 (베팅, 청산, 쿨타임)
│   ├── state_manager.py    # 상태 저장 (casino_state.json)
│   └── scanner.py          # 종목 선정 (현재는 랜덤)
├── exchange/
│   └── mexc.py             # MEXC API 커넥터
├── utils/
│   ├── telegram_bot.py     # 텔레그램 봇 (버튼 UI, 상태 조회)
│   └── logger.py           # 로깅 (일련번호 필터 적용)
└── logs/                   # 로그 및 메시지 히스토리 저장
```

## 3. Current Configuration (Game Mode)
**실제 MEXC API 연동 + 인터랙티브 선택 기능!**

- **Cycle**: `10분` (`CYCLE_MINUTES = 10`) - 테스트용
- **Coin Selection**: **공격적 전략 + 게임 요소**
    - 변동률: 15% ~ 40%
    - 거래대금: 100만불 이상
    - 모멘텀 스코어 상위 20개 중 3개 후보 제시
    - **사용자 선택**: 텔레그램 버튼으로 3개 중 1개 선택
    - **타임아웃**: 3분 내 미선택 시 자동 랜덤 선택
    - Fallback: 조건 완화 (10~40%, 50만불)
- **Price**: 실제 MEXC 시세 조회 (`mexc.get_ticker`)
- **Action Flow**:
    1.  **0분 00초**: 후보 3개 스캔 및 텔레그램 버튼 전송
    2.  **0~3분**: 사용자 선택 대기 (3분 후 자동 랜덤 선택)
    3.  **선택 완료**: 실제 시세로 진입
    4.  **9분 50초**: 실제 시세로 자동 청산
    5.  **10분 00초**: 쿨타임 해제 및 재매수
- **State Persistence**: 
    - `casino_state.json` 재시작 후에도 유지됨
    - 복구 및 동기화 로직으로 안전성 보장

## 4. Key Features
- **JobQueue**: `python-telegram-bot`의 JobQueue를 사용하여 안정적인 주기 실행.
- **Cooldown**: 매도 후 다음 주기까지 재진입 절대 불가.
- **Interactive Selection**: 
    - 후보 3개 제시 (InlineKeyboard 버튼)
    - 3분 선택 타임아웃 (자동 랜덤 선택)
    - 실시간 콜백 처리
- **State Recovery** (🆕):
    - 재시작 시 기존 포지션 자동 복구
    - `casino_state.json`을 진실의 원천(Source of Truth)으로 신뢰
    - 3가지 케이스 대응:
        1. 포지션 있음: 정상 복구 및 자동 청산 Job 계속 작동
        2. 선택 대기 중: 초기화 (3분 타임아웃 지났을 가능성)
        3. 포지션 없음: 정상 (새 사이클 대기)
    - ⚠️ 거래소 잔고 동기화 안 함 (수동 매수, XRP 입금용 등 구분 불가)
- **Telegram UI**: 
    - 메뉴: `상태`, `매도`, `도움말` 버튼
    - 게임: 인라인 버튼으로 종목 선택
- **Logging**:
    - `logs/casino_YYYY-MM-DD.log`: 실행 로그 (Seq No. 포함)
    - `logs/telegram_history_*.jsonl`: 보낸 메시지 원본 저장

## 5. Next Tasks (To Production Mode)
**출금 제한 해제 후 (D-Day)** 진행해야 할 작업입니다.

✅ **완료된 작업**:
- ~~`core/scanner.py` 수정~~ → 공격적 전략 + 다중 후보 선정 완료
- ~~실제 API 연동~~ → MEXC 시세 조회 연동 완료
- ~~게임 요소 추가~~ → 인터랙티브 선택 시스템 구현 완료

⏳ **남은 작업**:
1.  **`core/config.py` 수정**:
    - `CYCLE_HOURS = 48`
    - `CYCLE_MINUTES = 0`
2.  **`core/scheduler_engine.py` 수정**:
    - 실제 매수/매도 로직 활성화 (`mexc.create_market_buy`, `create_market_sell`)
    - `run_repeating` -> `run_daily(time=datetime.time(12, 0))` 로 변경 (정오 실행)
3.  **리스크 관리 추가**:
    - 주문 실패 시 재시도 로직
    - 잔고 부족 체크
    - 최소 주문 금액 검증

## 6. How to Run
```bash
# 가상환경 활성화
source venv/bin/activate

# 실행 (상태 자동 리셋됨)
python main.py
```

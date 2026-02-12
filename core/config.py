from datetime import datetime, timedelta

# ==========================================
# 🎰 Boracay Casino 설정 (Config)
# ==========================================

# 1. 운용 모드
# - "test": 테스트/검증용
# - "live": 실전용 (정오 시작 + 48시간 주기)
RUN_MODE = "test"  # "test" or "live"

# 1-1. 테스트 모드 설정
TEST_FIRST_TRADE_DELAY_MINUTES = 3
TEST_CYCLE_HOURS = 0
TEST_CYCLE_MINUTES = 10

# 1-2. 실전 모드 설정
LIVE_FIRST_TRADE_HOUR = 12
LIVE_FIRST_TRADE_MINUTE = 0
LIVE_CYCLE_HOURS = 48
LIVE_CYCLE_MINUTES = 0

# 2. 베팅 설정
BET_AMOUNT_USDT = 5.1

# 3. 게임 설정
CANDIDATE_COUNT = 3  # 후보 코인 개수
SELECTION_TIMEOUT = 180  # 선택 타임아웃 (초) - 3분

# 4. 타이밍 조정값
# - EARLY_EXIT_SECONDS: 자동 청산을 주기 종료보다 앞당기는 시간
# - COOLDOWN_RELEASE_BUFFER_SECONDS: 쿨타임 계산 버퍼
EARLY_EXIT_SECONDS = 10
COOLDOWN_RELEASE_BUFFER_SECONDS = 20

# 5. 주문 안전 설정
# - ENABLE_REAL_ORDERS: True일 때만 실제 주문 실행
# - MIN_ORDER_USDT: 최소 주문 금액(거래소 정책/안전 여유 반영)
# - BALANCE_BUFFER_USDT: 잔고 여유 버퍼 (수수료/슬리피지 대비)
# - ORDER_MAX_RETRIES / ORDER_RETRY_DELAY_SECONDS: 주문 재시도 정책
ENABLE_REAL_ORDERS = False
MIN_ORDER_USDT = 5.0
BALANCE_BUFFER_USDT = 0.2
ORDER_MAX_RETRIES = 3
ORDER_RETRY_DELAY_SECONDS = 2

# 6. 시작 프리체크 정책
# - 테스트 모드에서는 자동 차단을 끄고, 실운영 모드에서만 자동 차단 활성화
# - 수동 점검(텔레그램 "시작점검" 버튼)은 모드와 관계없이 사용 가능
STARTUP_PREFLIGHT_ENABLED = False

# ==========================================
# 🧮 자동 계산 (수정 불필요)
# ==========================================

def _next_daily_time(hour: int, minute: int) -> datetime:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


if RUN_MODE == "live":
    CYCLE_HOURS = LIVE_CYCLE_HOURS
    CYCLE_MINUTES = LIVE_CYCLE_MINUTES
    FIRST_TRADE_START_AT = _next_daily_time(
        LIVE_FIRST_TRADE_HOUR, LIVE_FIRST_TRADE_MINUTE
    ).strftime("%Y-%m-%d %H:%M:%S")
    MODE_STRING = "LIVE"
    STARTUP_PREFLIGHT_ENABLED = True
else:
    CYCLE_HOURS = TEST_CYCLE_HOURS
    CYCLE_MINUTES = TEST_CYCLE_MINUTES
    FIRST_TRADE_START_AT = (
        datetime.now().replace(microsecond=0)
        + timedelta(minutes=TEST_FIRST_TRADE_DELAY_MINUTES)
    ).strftime("%Y-%m-%d %H:%M:%S")
    MODE_STRING = "TEST"
    STARTUP_PREFLIGHT_ENABLED = False

# 총 주기 (Timedelta 객체)
CYCLE_DELTA = timedelta(hours=CYCLE_HOURS, minutes=CYCLE_MINUTES)

# 총 주기 (초 단위 - JobQueue용)
CYCLE_SECONDS = int(CYCLE_DELTA.total_seconds())

# 사람이 읽기 좋은 주기 문자열
if CYCLE_HOURS > 0 and CYCLE_MINUTES > 0:
    CYCLE_STRING = f"{CYCLE_HOURS}시간 {CYCLE_MINUTES}분"
elif CYCLE_HOURS > 0:
    CYCLE_STRING = f"{CYCLE_HOURS}시간"
else:
    CYCLE_STRING = f"{CYCLE_MINUTES}분"

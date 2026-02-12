from datetime import timedelta

# ==========================================
# 🎰 Boracay Casino 설정 (Config)
# ==========================================

# 1. 운용 주기 설정 (시간 + 분 합산)
# 예: 48시간 0분 (실전), 0시간 10분 (테스트)
CYCLE_HOURS = 0
CYCLE_MINUTES = 10

# 2. 베팅 설정
BET_AMOUNT_USDT = 5.1

# 3. 게임 설정
CANDIDATE_COUNT = 3  # 후보 코인 개수
SELECTION_TIMEOUT = 180  # 선택 타임아웃 (초) - 3분

# ==========================================
# 🧮 자동 계산 (수정 불필요)
# ==========================================

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

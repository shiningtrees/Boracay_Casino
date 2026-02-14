# 🎰 Boracay Casino: Trailing Stop Strategy Specification

> **Status**: ✅ 구현 완료 (2026-02-14)

## 1. 개요
수익을 극대화하기 위해 +25% 도달 시점부터 트레일링 스탑을 활성화하여 수익을 추격(Trailing)한다.

## 2. 주요 설정 (core/config.py)
- `STOP_LOSS_THRESHOLD = -25.0`   # 원금 대비 -25% 시 즉시 손절
- `TS_ACTIVATION_REWARD = 25.0`   # 수익률 +25% 도달 시 트레일링 스탑 활성화
- `TS_CALLBACK_RATE = 10.0`      # 최고점(Peak) 대비 10% 하락 시 익절 매도
- `CHECK_INTERVAL = 300`          # 감시 주기 (5분/300초)

## 3. 핵심 로직 (core/scheduler_engine.py)
- **손절 감시:** 수익률이 -25% 이하로 떨어지면 무조건 즉시 매도. ✅
- **트레일링 활성화:** 수익률이 +25%를 터치하면 `is_ts_active`를 True로 바꾸고 이때의 가격을 `peak_price`로 기록. ✅
- **고점 갱신:** 활성화 상태에서 현재가가 `peak_price`보다 높으면 계속 최신화. ✅
- **익절 실행:** 현재가가 `peak_price` 대비 10% 하락하면(`current <= peak * 0.9`) 즉시 매도 후 수익 확정. ✅

## 4. 구현 완료 사항 (2026-02-14)
- `core/config.py`: 손절/익절 설정값 추가
- `core/state_manager.py`: 트레일링 상태 관리 (`trailing_stop`)
- `core/scheduler_engine.py`: `check_48h_exit_callback()` 확장
  - 손절 체크 로직
  - 트레일링 활성화 로직
  - 최고가 추적 및 익절 로직
- `main.py`: 감시 주기 5분으로 설정, 부팅 알림 추가
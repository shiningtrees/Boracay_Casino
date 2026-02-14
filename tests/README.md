# 🧪 Backtest Engine

> Boracay Casino 트레일링 스탑 전략 백테스트 엔진

---

## 개요

실전 트레일링 스탑 전략과 100% 동기화된 백테스트 엔진.
48h, 72h, 96h 주기별로 생존성과 수익성을 비교 분석한다.

---

## 주요 특징

### 1. 실전 로직 동기화
- 손절: -25% 도달 시 즉시 매도
- 트레일링 활성화: +25% 도달 시 peak 추적
- 익절: peak 대비 10% 하락 시 매도
- 타임아웃: 설정 주기 경과 시 청산

### 2. 스캐너 모드 (실전과 동일) ⭐
- **매 사이클마다 새로운 코인 선정**
- 변동률 +15~40%, 거래대금 $100만 이상 필터링
- 상위 20개 중 랜덤 선택
- 실전 알트코인 변동성 재현

### 3. 데이터 정밀도
- **OHLCV 5분봉** 사용
- **High/Low 기준** 손절/익절 체크
- 종가만 보는 것이 아니라 캔들 내부 변동 반영

### 4. 거래 비용
- 진입/청산 각 0.15% 수수료
- 총 0.3% 거래 비용 반영

### 5. 마이너스 잔고 허용
- 잔고 부족해도 시뮬레이션 계속 진행
- 전체 기간 분석 완주

---

## 사용법

### 기본 실행 (단일 심볼)
```bash
python run_backtest.py BTC/USDT 2024-01-01 2024-12-31
```

### 스캐너 모드 (실전과 동일) ⭐ 권장
```bash
# 매 사이클마다 스캐너로 상위 20개 중 랜덤 선택
python run_backtest.py SCANNER 2026-02-12 2026-02-14 --cycles 48,72,96

# 또는
python run_backtest.py BTC/USDT 2026-02-12 2026-02-14 --scanner
```

### 주기 커스터마이징
```bash
python run_backtest.py ETH/USDT 2024-06-01 2024-12-31 --cycles 24,48,72
```

### 출력 파일 지정
```bash
python run_backtest.py BTC/USDT 2024-01-01 2024-12-31 -o results/btc_2024.json
```

---

## 출력 리포트 항목

### A. 수익성 분석
- 최종 잔고 및 총 손익 (USDT, %)
- 최고 잔고 (ATH)
- 평균 수익률 (전체/승/패)

### B. 거래 통계
- 총 거래 횟수
- 승률 (winning trades / total trades)
- 청산 사유별 분포 (stop_loss, trailing_stop, timeout)

### C. 생존 분석
- 생존 일수
- 파산 지점 (잔고 < 5.1 USDT 도달 시점)
- 파산까지 거래 횟수

### D. 최대 잭팟
- 단일 종목 최고 수익률
- 청산 사유 및 시점

### E. 최종 추천
- 최고 수익 주기
- 최장 생존 주기

---

## 백테스트 설정

`tests/backtester.py`의 `BacktestConfig` 클래스에서 설정 가능:

```python
class BacktestConfig:
    INITIAL_BALANCE = 100.0          # 초기 자산
    BET_AMOUNT = 5.1                 # 베팅 금액
    STOP_LOSS_THRESHOLD = -25.0      # 손절 기준
    TS_ACTIVATION_REWARD = 25.0      # 트레일링 활성화
    TS_CALLBACK_RATE = 10.0          # 익절 콜백
    TRADING_FEE_PERCENT = 0.3        # 거래 비용
    TEST_CYCLES = [48, 72, 96]       # 테스트 주기
```

---

## 결과 파일 형식

JSON 형식으로 저장:
```json
{
  "symbol": "BTC/USDT",
  "period": "2024-01-01 ~ 2024-12-31",
  "results": {
    "48h": {
      "initial_balance": 100.0,
      "final_balance": 127.5,
      "total_pnl": 27.5,
      "win_rate": 65.5,
      "survival_days": 180,
      "trades": [...]
    },
    "72h": {...},
    "96h": {...}
  },
  "recommendation": {
    "best_profit_cycle": "48h",
    "longest_survival_cycle": "72h"
  }
}
```

---

## 주의사항

### 1. 데이터 크기
- 1년치 5분봉 = ~105,000 캔들
- 다운로드 시간: 심볼당 1~3분 소요

### 2. API 제한
- MEXC 공개 API는 rateLimit 적용
- 여러 심볼 연속 실행 시 간격 두기

### 3. 재현성
- 코인 선택이 랜덤이므로 완전한 재현 불가
- 여러 번 실행하여 경향성 파악

---

## 예제

### 스캐너 모드 (실전과 동일)
```bash
# 권장: 실전처럼 매 사이클 랜덤 코인 선택
python run_backtest.py SCANNER 2026-02-12 2026-02-14 --cycles 48,72,96
```

### 단일 심볼 테스트
```bash
# 최근 3개월 BTC 백테스트
python run_backtest.py BTC/USDT 2024-10-01 2024-12-31
```

### 여러 주기 비교
```bash
# 24h, 48h, 72h, 96h 모두 테스트
python run_backtest.py SCANNER 2026-02-07 2026-02-14 --cycles 24,48,72,96
```

### 파이썬 코드에서 직접 실행
```python
from tests.backtester import run_multi_cycle_backtest, print_summary_report

# 스캐너 모드
summary = run_multi_cycle_backtest('SCANNER', '2026-02-12', '2026-02-14', use_scanner=True)
print_summary_report(summary)

# 단일 심볼
summary = run_multi_cycle_backtest('BTC/USDT', '2024-01-01', '2024-12-31', use_scanner=False)
print_summary_report(summary)
```

---

## 문제 해결

### Q: 데이터 다운로드 실패
A: 네트워크 확인 또는 MEXC API 상태 확인

### Q: 메모리 부족
A: 기간을 짧게 나눠서 실행 (예: 3개월씩)

### Q: 주기가 너무 길어서 거래 횟수가 적음
A: 분석 기간을 늘리거나 짧은 주기 추가

---

**Last Updated**: 2026-02-14

# 🎰 Boracay Casino - 실전 운영 준비 완료

## ✅ 최종 설정

### 거래소
**MEXC** (잡코인 2,285개)

### 운영 주기
**72시간 (3일)** ⭐

### 전략
- 손절: -25%
- 트레일링 활성화: +25%
- 익절: peak 대비 10% 하락
- 감시 주기: 5분

### 초기 자금
**100 USDT**

---

## 📊 백테스트 결과 (Binance 13개월)

```
48h: -11.30% (158거래, 승률 41.77%)
72h: -13.34% (97거래, 승률 44.33%) ⭐ 선택
96h: -0.71% (76거래, 승률 47.37%)
```

**72h 선택 이유:**
- 연 -10% 손실 → 7~10년 생존 가능
- 3일마다 거래 → 재미 + 학습
- MEXC 잡코인으로 더 나을 것 예상

---

## 🚀 실행 명령

### 봇 시작
```bash
cd /Users/ohs/GitHub/Boracay_Casino
rm -f .boracay_casino_bot.lock
source venv/bin/activate
python main.py 2>&1
```

### 봇 종료 (안전)
```bash
# 1. PID 확인
ps aux | grep 'python main.py' | grep -v grep

# 2. 종료
kill -9 <PID>
sleep 5
rm -f .boracay_casino_bot.lock
```

---

## 📱 텔레그램 명령

- **📊 상태**: 현재 포지션, 수익률
- **💰 매도**: 수동 청산
- **❓ 도움말**: 사용법

---

## 📁 주요 파일

### 설정
- `core/config.py` - 주기 72h 설정됨
- `.env` - MEXC API 키

### 로그
- `logs/casino_YYYY-MM-DD.log` - 일별 로그
- `casino_state.json` - 현재 상태

### 백테스트
- `tests/backtester.py` - MEXC 백테스트
- `tests/binance_backtest.py` - Binance 백테스트
- `run_backtest.py` - CLI 실행

---

## 🎯 운영 목표

### 주 목표
- ✅ 100 USDT로 수년간 버티기
- ✅ 3일마다 코인 선택의 재미
- ✅ 트레이딩 학습
- ✅ 가끔 대박의 쾌감

### NOT 목표
- ❌ 돈 벌기
- ❌ 전업 트레이더
- ❌ 큰 돈 투자

---

## 📈 예상 시나리오

### 최선
- 연 +10~20% 수익
- 트레일링 자주 발동

### 평균 ⭐
- 연 -10% 손실
- 7~10년 생존

### 최악
- 연 -30% 손실
- 3~4년 생존

**어쨌든 당분간 안 망함!** ✅

---

## ⚠️ 주의사항

1. **소액 운영**
   - 초기 100 USDT
   - 잃어도 커피값

2. **학습 목적**
   - 수익 기대 금지
   - 재미 + 경험 중심

3. **데이터 수집**
   - 3개월 후 실전 vs 백테스트 비교
   - 필요시 파라미터 조정

---

## 📚 문서 위치

### 개발 문서
- `DEV_NOTES.md` - 메인 개발 문서
- `docs/README.md` - 문서 구조 가이드

### 작업 일지
- `docs/changelog/2026-02-14.md` - 트레일링 스탑
- `docs/changelog/2026-02-14-part2-backtest.md` - 백테스트 엔진
- `docs/changelog/2026-02-14-part3-backtest-results.md` - 실행 결과
- `docs/changelog/2026-02-14-part4-scanner-mode.md` - 스캐너 모드
- `docs/changelog/2026-02-14-longterm-backtest.md` - 장기 백테스트
- `docs/changelog/2026-02-14-final-decision.md` - 최종 결정
- `docs/changelog/2026-02-14-data-limitation.md` - 데이터 제약

### 배포 가이드
- `docs/deploy/SERVER_DEPLOY.md` - 서버 배포
- `docs/deploy/ORIGINAL_ONLY_WORKFLOW.md` - 워크플로우

---

## ✅ 체크리스트

- [x] 트레일링 스탑 전략 구현
- [x] 백테스트 엔진 구현
- [x] MEXC 백테스트 (2일)
- [x] Binance 백테스트 (13개월)
- [x] 72h 주기 결정
- [x] config.py 설정
- [x] 모든 문서 업데이트
- [ ] MEXC 충전
- [ ] 실전 운영 시작
- [ ] Docker 배포

---

## 🎉 준비 완료!

**모든 설정이 완료되었습니다.**

**다음 단계:**
1. MEXC 충전 (100 USDT)
2. 봇 시작
3. 첫 거래 대기 (정오 12:00)
4. 3일마다 재미!

**행운을 빕니다!** 🍀🎰

---

**최종 업데이트**: 2026-02-14  
**주기**: 72h (3일)  
**거래소**: MEXC  
**상태**: ✅ 실전 준비 완료

# Boracay Casino Open Checklist

## 1) Mode And Schedule
- [ ] `core/config.py`에서 `RUN_MODE = "live"`로 전환
- [ ] `LIVE_FIRST_TRADE_HOUR = 12`, `LIVE_FIRST_TRADE_MINUTE = 0` 확인
- [ ] `LIVE_CYCLE_HOURS = 48`, `LIVE_CYCLE_MINUTES = 0` 확인
- [ ] 부팅 로그에 `Mode/LIVE`, `First Start`, `Cycle` 출력 확인

## 2) Timing Safety
- [ ] `EARLY_EXIT_SECONDS` 값 확정 (기본 10초)
- [ ] `COOLDOWN_RELEASE_BUFFER_SECONDS` 값 확정 (기본 20초)
- [ ] 상태/복구/자동청산 계산이 동일 변수 사용 중인지 확인

## 3) Real Order Safety
- [ ] 매수 주문 파라미터(금액/수량 기준) 재검증
- [ ] 매도 주문 파라미터 재검증
- [ ] 주문 실패 재시도 정책 정의 (횟수/간격/중단 조건)
- [ ] 잔고 부족/최소 주문 금액 검증 로직 점검

## 4) Recovery And Restart
- [ ] 재시작 시 `active_bet` 정상 복구 확인
- [ ] 만기 경과 포지션 즉시 청산 확인
- [ ] `pending_selection` 초기화/복구 처리 확인
- [ ] 중복 진입/중복 청산 방지 확인

## 5) Telegram UX
- [ ] `상태` 메시지에 현재 상태/청산예정/잔여시간 표시 확인
- [ ] 매수/매도 완료 메시지 포맷 통일 확인
- [ ] 오류 메시지 발생 시 하단 메뉴 버튼 복구 확인

## 6) Dry Run Before Live
- [ ] 테스트 모드 24시간 무중단 실행
- [ ] 강제 재시작 시나리오(진입 전/후/청산 직전) 점검
- [ ] 네트워크 오류/거래소 오류 상황에서 안전 종료 확인

## 7) Go Live
- [ ] 실전 전환 직전 백업: `.env`, `casino_state.json`, 최근 로그
- [ ] 오픈 당일 첫 정오 진입 1회 수동 모니터링
- [ ] 이상징후 기준과 즉시 중지 절차 문서화

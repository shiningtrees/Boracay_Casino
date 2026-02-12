import asyncio
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from core.state_manager import StateManager
from core.scanner import MarketScanner
from utils.logger import logger
import core.config as config

class CasinoScheduler:
    def __init__(self, mexc, bot=None):
        self.mexc = mexc
        self.bot = bot 
        self.state = StateManager()
        self.scanner = MarketScanner(mexc)
        logger.info(f"⚙️ 스케줄러 엔진 초기화 완료 (Cycle: {config.CYCLE_STRING})")

    def build_preflight_report(self):
        """실주문 전환 전 필수 점검 리포트 생성."""
        checks = []
        ok = True

        # 공통 체크
        if config.CYCLE_SECONDS <= 0:
            checks.append("❌ 주기 설정 오류: CYCLE_SECONDS <= 0")
            ok = False
        else:
            checks.append(f"✅ 주기 설정: {config.CYCLE_STRING} ({config.CYCLE_SECONDS}초)")

        try:
            datetime.strptime(config.FIRST_TRADE_START_AT, "%Y-%m-%d %H:%M:%S")
            checks.append(f"✅ 시작 시각 파싱: {config.FIRST_TRADE_START_AT}")
        except Exception:
            checks.append(f"❌ 시작 시각 파싱 실패: {config.FIRST_TRADE_START_AT}")
            ok = False

        if config.BET_AMOUNT_USDT < config.MIN_ORDER_USDT:
            checks.append(
                f"❌ 최소 주문 금액 미달: BET {config.BET_AMOUNT_USDT} < MIN {config.MIN_ORDER_USDT}"
            )
            ok = False
        else:
            checks.append(
                f"✅ 최소 주문 금액: BET {config.BET_AMOUNT_USDT} >= MIN {config.MIN_ORDER_USDT}"
            )

        total_usdt, free_usdt = self.mexc.get_balance()
        required = config.BET_AMOUNT_USDT + config.BALANCE_BUFFER_USDT
        if free_usdt < required:
            checks.append(
                f"❌ 잔고 부족: Free {free_usdt:.2f} < Required {required:.2f} "
                f"(Bet {config.BET_AMOUNT_USDT:.2f} + Buffer {config.BALANCE_BUFFER_USDT:.2f})"
            )
            ok = False
        else:
            checks.append(
                f"✅ 잔고 확인: Free {free_usdt:.2f} >= Required {required:.2f}"
            )

        # 실주문 모드 추가 체크
        if config.ENABLE_REAL_ORDERS:
            if config.RUN_MODE != "live":
                checks.append("❌ 실주문 보호: ENABLE_REAL_ORDERS=True 이면 RUN_MODE='live' 필요")
                ok = False
            else:
                checks.append("✅ 실주문 모드 보호: RUN_MODE=live 확인")

        return ok, checks

    def _format_duration_ko(self, total_seconds: float) -> str:
        seconds = max(0, int(total_seconds))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{days}일 {hours}시간 {minutes}분 {secs}초"

    def _balance_snapshot_text(self):
        total_usdt, free_usdt = self.mexc.get_balance()
        return f"💰 Balance: {free_usdt:.2f} / {total_usdt:.2f} USDT (Free/Total)"

    async def _create_market_buy_with_retry(self, symbol: str, amount_usdt: float):
        last_error = None
        for attempt in range(1, config.ORDER_MAX_RETRIES + 1):
            order = self.mexc.create_market_buy(symbol, amount_usdt)
            if order:
                return order
            last_error = f"attempt={attempt}"
            if attempt < config.ORDER_MAX_RETRIES:
                await asyncio.sleep(config.ORDER_RETRY_DELAY_SECONDS)
        logger.error(f"❌ 매수 재시도 실패 ({symbol}): {last_error}")
        return None

    async def _create_market_sell_with_retry(self, symbol: str):
        last_error = None
        for attempt in range(1, config.ORDER_MAX_RETRIES + 1):
            order = self.mexc.create_market_sell(symbol)
            if order:
                return order
            last_error = f"attempt={attempt}"
            if attempt < config.ORDER_MAX_RETRIES:
                await asyncio.sleep(config.ORDER_RETRY_DELAY_SECONDS)
        logger.error(f"❌ 매도 재시도 실패 ({symbol}): {last_error}")
        return None

    @staticmethod
    def _extract_order_price(order, fallback_price):
        if not order:
            return fallback_price
        price = order.get("average") or order.get("price")
        if price:
            return float(price)
        return fallback_price

    async def job_daily_bet_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """JobQueue에 의해 실행되는 베팅 로직 (게임 모드)"""
        now = datetime.now()
        logger.info(f"🕛 [Job] 베팅 잡 실행 (Time: {now})")

        # -1. 첫 거래 시작 시각 이전에는 대기
        try:
            first_start_at = datetime.strptime(config.FIRST_TRADE_START_AT, "%Y-%m-%d %H:%M:%S")
            if now < first_start_at:
                remain_text = self._format_duration_ko((first_start_at - now).total_seconds())
                logger.info(
                    f"🕒 [Wait] 첫 거래 시작 대기 중 "
                    f"(Start: {config.FIRST_TRADE_START_AT}, 남은 시간: {remain_text})"
                )
                return
        except Exception as e:
            logger.warning(f"⚠️ 시작 시각 파싱 실패. 게이트 없이 진행합니다. ({e})")
        
        # 마지막 베팅 Job 시간 저장
        self.state.set_last_bet_job_time()
        
        # 0. 쿨타임 체크
        cooldown_until = self.state.get_cooldown()
        if cooldown_until:
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            if now_str < cooldown_until:
                logger.info(f"🧊 [Skip] 쿨타임 중입니다. (현재: {now_str} < 해제: {cooldown_until})")
                return
            else:
                logger.info("🔥 쿨타임 해제됨. 베팅 시도.")
                self.state.state["cooldown_until"] = None
                self.state.save_state()
        
        # 1. 진행 중인 베팅 확인
        active = self.state.get_active_bet()
        if active:
            logger.info(f"⚠️ [Skip] 이미 진행 중인 게임이 있습니다: {active['symbol']}")
            return

        # 2. 후보 선택 대기 중인지 확인
        pending = self.state.get_pending_selection()
        if pending:
            logger.info("⚠️ [Skip] 이미 후보 선택 대기 중입니다.")
            return

        # 3. 후보 코인 스캔 (3개)
        candidates = self.scanner.find_candidates(config.CANDIDATE_COUNT)
        
        if not candidates:
            logger.error("❌ [Scanner] 조건에 맞는 후보를 찾지 못했습니다. 이번 사이클 스킵.")
            return
        
        # 4. 후보 선택 대기 상태 저장
        self.state.set_pending_selection(candidates)
        
        # 5. 텔레그램으로 후보 전송 (버튼 포함)
        chat_id = context.job.chat_id or context.job.data
        
        if chat_id and self.bot:
            try:
                # 버튼과 함께 메시지 전송 (bot 인스턴스 활용)
                await self.bot.send_candidate_selection(candidates, chat_id)
                
                # 6. 타임아웃 Job 등록 (3분 후 자동 선택)
                context.job_queue.run_once(
                    self.selection_timeout_callback,
                    when=config.SELECTION_TIMEOUT,
                    data=chat_id,
                    chat_id=chat_id,
                    name="selection_timeout"
                )
                logger.info(f"⏰ 선택 타임아웃 Job 등록 ({config.SELECTION_TIMEOUT}초)")
                
            except Exception as e:
                logger.error(f"❌ 후보 전송 실패: {e}")
                self.state.clear_pending_selection()
        else:
            logger.error("❌ CHAT_ID 또는 Bot 인스턴스 누락")
            self.state.clear_pending_selection()
    
    async def selection_timeout_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """선택 타임아웃 처리 (3분 경과 시 자동 랜덤 선택)"""
        logger.info("⏰ [Timeout] 선택 시간 초과. 자동 랜덤 선택 실행.")
        
        pending = self.state.get_pending_selection()
        if not pending:
            logger.warning("⚠️ 타임아웃 시점에 pending 상태 없음. 스킵.")
            return
        
        candidates = pending.get("candidates", [])
        if not candidates:
            logger.error("❌ 후보 목록이 비어있음.")
            self.state.clear_pending_selection()
            return
        
        # 랜덤 선택
        import random
        selected = random.choice(candidates)
        logger.info(f"🎲 [Auto] 랜덤 선택: {selected['symbol']}")
        
        # 진입 처리
        await self._execute_entry(selected, context, auto=True)
    
    async def execute_user_selection(self, symbol, context: ContextTypes.DEFAULT_TYPE):
        """사용자가 선택한 종목으로 진입"""
        logger.info(f"👤 [User] 사용자 선택: {symbol}")
        
        pending = self.state.get_pending_selection()
        if not pending:
            logger.warning("⚠️ 선택 가능한 상태가 아님.")
            return False
        
        candidates = pending.get("candidates", [])
        selected = next((c for c in candidates if c['symbol'] == symbol), None)
        
        if not selected:
            logger.error(f"❌ 선택한 종목이 후보 목록에 없음: {symbol}")
            return False
        
        # 타임아웃 Job 취소
        current_jobs = context.job_queue.get_jobs_by_name("selection_timeout")
        for job in current_jobs:
            job.schedule_removal()
            logger.info("🛑 타임아웃 Job 취소됨")
        
        # 진입 처리
        await self._execute_entry(selected, context, auto=False)
        return True
    
    async def _execute_entry(self, selected, context, auto=False):
        """실제 진입 처리 (공통 로직)"""
        symbol = selected['symbol']
        
        # 현재가 조회
        current_price = self.mexc.get_ticker(symbol)
        if not current_price:
            logger.error(f"❌ [MEXC] 시세 조회 실패: {symbol}. 스킵.")
            self.state.clear_pending_selection()
            return
        
        logger.info(f"🎯 진입 확정: {symbol} @ ${current_price}")

        # 주문 안전 가드: 최소 주문 금액
        if config.BET_AMOUNT_USDT < config.MIN_ORDER_USDT:
            logger.error(
                f"❌ [Guard] 최소 주문 금액 미달: {config.BET_AMOUNT_USDT} < {config.MIN_ORDER_USDT}"
            )
            self.state.clear_pending_selection()
            if self.bot:
                await self.bot.send_message(
                    f"❌ [진입 스킵] 최소 주문 금액 미달\n"
                    f"Configured: {config.BET_AMOUNT_USDT} USDT\n"
                    f"Required: {config.MIN_ORDER_USDT} USDT"
                )
            return

        # 주문 안전 가드: 잔고 부족 체크
        total_usdt, free_usdt = self.mexc.get_balance()
        required_usdt = config.BET_AMOUNT_USDT + config.BALANCE_BUFFER_USDT
        if free_usdt < required_usdt:
            logger.error(
                f"❌ [Guard] 잔고 부족: Free={free_usdt} < Required={required_usdt}"
            )
            self.state.clear_pending_selection()
            if self.bot:
                await self.bot.send_message(
                    f"❌ [진입 스킵] 잔고 부족\n"
                    f"Free: {free_usdt:.2f} USDT\n"
                    f"Need: {required_usdt:.2f} USDT "
                    f"(Bet {config.BET_AMOUNT_USDT:.2f} + Buffer {config.BALANCE_BUFFER_USDT:.2f})"
                )
            return

        order = None
        if config.ENABLE_REAL_ORDERS:
            order = await self._create_market_buy_with_retry(symbol, config.BET_AMOUNT_USDT)
            if not order:
                self.state.clear_pending_selection()
                if self.bot:
                    await self.bot.send_message(
                        f"❌ [진입 실패] 주문 재시도 초과\n"
                        f"Symbol: {symbol}\n"
                        f"Bet: {config.BET_AMOUNT_USDT} USDT"
                    )
                return
            logger.info(f"✅ [Order] 매수 주문 성공: {order.get('id', 'N/A')}")

        final_entry_price = self._extract_order_price(order, current_price)

        # 상태 저장 (주문 성공/검증 완료 후 저장)
        self.state.set_active_bet(symbol, final_entry_price, config.BET_AMOUNT_USDT)
        self.state.clear_pending_selection()
        
        # 알림 전송
        mode_text = "🎲 [자동 선택]" if auto else "✅ [선택 완료]"
        msg = (
            f"{mode_text}\n"
            f"🎯 Symbol: {symbol}\n"
            f"💵 Entry: ${final_entry_price}\n"
            f"💰 Amount: {config.BET_AMOUNT_USDT} USDT\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 Change: +{selected['change']:.2f}%\n"
            f"📌 Rule: {config.CYCLE_STRING} 뒤 자동 청산\n"
            f"🧪 Order Mode: {'LIVE' if config.ENABLE_REAL_ORDERS else 'PAPER'}\n"
            f"{self._balance_snapshot_text()}"
        )
        
        if self.bot:
            await self.bot.send_message(msg)
        else:
            # fallback
            try:
                chat_id = context.job.chat_id if hasattr(context, 'job') else None
                if chat_id:
                    await context.bot.send_message(chat_id=chat_id, text=msg)
            except Exception as e:
                logger.error(f"❌ 메시지 전송 실패: {e}")

    async def check_48h_exit_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """JobQueue에 의해 실행되는 자동 청산 로직"""
        logger.debug("🔎 [Job] 자동 청산 조건 체크 중...")
        
        active = self.state.get_active_bet()
        if not active:
            return

        entry_time = datetime.strptime(active["entry_time"], "%Y-%m-%d %H:%M:%S")
        # 주기보다 N초 일찍 청산
        exit_time = entry_time + config.CYCLE_DELTA - timedelta(seconds=config.EARLY_EXIT_SECONDS)
        now = datetime.now()
        
        if now >= exit_time:
            logger.info(f"⏰ 시간 만료 감지! (Entry: {entry_time} -> Exit: {exit_time})")
            logger.info(f"🗑️ 자동 청산 실행: {active['symbol']}")
            
            # 실제 현재가 조회
            current_price = self.mexc.get_ticker(active['symbol'])
            if not current_price:
                logger.error(f"❌ 시세 조회 실패. 진입가 기준으로 청산 처리.")
                current_price = active['entry_price']

            if config.ENABLE_REAL_ORDERS:
                sell_order = await self._create_market_sell_with_retry(active['symbol'])
                if not sell_order:
                    logger.error("❌ [Order] 자동 청산 주문 실패. 상태 유지.")
                    if self.bot:
                        await self.bot.send_message(
                            f"❌ [자동 청산 실패] 주문 재시도 초과\n"
                            f"Symbol: {active['symbol']}\n"
                            f"포지션 상태는 유지됩니다."
                        )
                    return
                current_price = self._extract_order_price(sell_order, current_price)
                logger.info(f"✅ [Order] 자동 매도 주문 성공: {sell_order.get('id', 'N/A')}")
            
            result = self.state.clear_active_bet(current_price, reason="timeout")
            pnl = result['pnl_percent']
            emoji = "🎉" if pnl > 0 else "💧"
            
            msg = (
                f"⏰ [타임아웃] 자동 청산 ({config.CYCLE_STRING} 경과)\n"
                f"{emoji} PNL: {pnl:+.2f}%\n"
                f"Entry: ${active['entry_price']}\n"
                f"Exit: ${current_price}\n"
                f"💤 다음 사이클까지 휴식합니다.\n"
                f"{self._balance_snapshot_text()}"
            )
            
            # 봇 인스턴스 활용하여 로깅 남기기
            if self.bot:
                await self.bot.send_message(msg)
            elif context.job.chat_id:
                chat_id = context.job.chat_id
                await context.bot.send_message(chat_id=chat_id, text=msg)

    def force_sell(self):
        """수동 매도 (텔레그램 핸들러에서 호출)"""
        logger.info("🚨 사용자에 의한 긴급 청산 요청(Force Sell)")
        
        active = self.state.get_active_bet()
        if not active:
            logger.warning("⚠️ 청산할 베팅이 없음")
            return "⚠️ 현재 진행 중인 베팅이 없습니다."

        logger.info(f"🚨 긴급 청산 실행: {active['symbol']}")
        
        # 실제 현재가 조회
        current_price = self.mexc.get_ticker(active['symbol'])
        if not current_price:
            logger.error(f"❌ 시세 조회 실패. 수동 매도 취소.")
            return "❌ 시세 조회 실패. 다시 시도해주세요."

        if config.ENABLE_REAL_ORDERS:
            sell_order = self.mexc.create_market_sell(active['symbol'])
            if not sell_order:
                logger.error("❌ [Order] 수동 매도 주문 실패. 상태 유지.")
                return "❌ [수동 청산 실패] 주문이 체결되지 않았습니다. 상태를 유지합니다."
            current_price = self._extract_order_price(sell_order, current_price)

        # 청산 처리 (쿨타임도 함께 해제됨)
        result = self.state.clear_active_bet(current_price, reason="user_request")
        pnl = result['pnl_percent']
        emoji = "🎉" if pnl > 0 else "💧"
        
        # 다음 베팅 시간 계산
        next_bet = self.state.get_next_bet_time()
        if next_bet:
            now = datetime.now()
            remaining = next_bet - now
            remaining_minutes = int(remaining.total_seconds() / 60)
            remaining_seconds = int(remaining.total_seconds() % 60)
            
            next_bet_str = next_bet.strftime("%H:%M:%S")
            time_str = f"⏰ 다음 베팅: {next_bet_str} (약 {remaining_minutes}분 {remaining_seconds}초 후)"
        else:
            time_str = "⏰ 다음 베팅: 곧 시작"
        
        return (
            f"✅ [수동 청산 완료]\n"
            f"{emoji} PNL: {pnl:+.2f}%\n"
            f"Entry: ${active['entry_price']}\n"
            f"Exit: ${current_price}\n"
            f"🔥 쿨타임 해제됨\n"
            f"{time_str}\n"
            f"{self._balance_snapshot_text()}"
        )

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

    async def job_daily_bet_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """JobQueue에 의해 실행되는 베팅 로직 (게임 모드)"""
        now = datetime.now()
        logger.info(f"🕛 [Job] 베팅 잡 실행 (Time: {now})")
        
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
        
        # 상태 저장
        self.state.set_active_bet(symbol, current_price, config.BET_AMOUNT_USDT)
        self.state.clear_pending_selection()
        
        # 알림 전송
        mode_text = "🎲 [자동 선택]" if auto else "✅ [선택 완료]"
        msg = (
            f"{mode_text}\n"
            f"🎯 Symbol: {symbol}\n"
            f"💵 Entry: ${current_price}\n"
            f"💰 Amount: {config.BET_AMOUNT_USDT} USDT\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 Change: +{selected['change']:.2f}%\n"
            f"📌 Rule: {config.CYCLE_STRING} 뒤 자동 청산"
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
        # POC: 주기보다 10초 일찍 청산하여 다음 주기에 바로 진입 가능하게 함
        exit_time = entry_time + config.CYCLE_DELTA - timedelta(seconds=10)
        now = datetime.now()
        
        if now >= exit_time:
            logger.info(f"⏰ 시간 만료 감지! (Entry: {entry_time} -> Exit: {exit_time})")
            logger.info(f"🗑️ 자동 청산 실행: {active['symbol']}")
            
            # 실제 현재가 조회
            current_price = self.mexc.get_ticker(active['symbol'])
            if not current_price:
                logger.error(f"❌ 시세 조회 실패. 진입가 기준으로 청산 처리.")
                current_price = active['entry_price']
            
            result = self.state.clear_active_bet(current_price, reason="timeout")
            pnl = result['pnl_percent']
            emoji = "🎉" if pnl > 0 else "💧"
            
            msg = (
                f"⏰ [타임아웃] 자동 청산 ({config.CYCLE_STRING} 경과)\n"
                f"{emoji} PNL: {pnl:+.2f}%\n"
                f"Entry: ${active['entry_price']}\n"
                f"Exit: ${current_price}\n"
                f"💤 다음 사이클까지 휴식합니다."
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

        result = self.state.clear_active_bet(current_price, reason="user_request")
        pnl = result['pnl_percent']
        emoji = "🎉" if pnl > 0 else "💧"
        cooldown_until = self.state.get_cooldown()
        
        return (
            f"✅ [수동 청산 완료]\n"
            f"{emoji} PNL: {pnl:+.2f}%\n"
            f"Entry: ${active['entry_price']}\n"
            f"Exit: ${current_price}\n"
            f"🧊 쿨타임: ~{cooldown_until}"
        )

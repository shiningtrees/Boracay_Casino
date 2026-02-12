import os
from dotenv import load_dotenv
from telegram.ext import Application
from exchange.mexc import MexcConnector
from utils.telegram_bot import CasinoBot
from core.scheduler_engine import CasinoScheduler
from utils.logger import logger
import core.config as config

# 환경변수 로드
load_dotenv()

# 전역 변수
mexc = None
bot = None
casino = None

async def on_startup(application):
    """봇 시작 시 실행: Job 등록, 복구 및 동기화"""
    global mexc, bot, casino
    
    logger.info("🤖 텔레그램 봇 시작 (Post-Init)...")
    
    # 잔고 조회
    balance, free = mexc.get_balance()
    logger.info(f"💰 MEXC 잔고: {balance} USDT (Free: {free} USDT)")
    
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    # ========================================
    # 🔄 상태 복구 로직 (봇 상태만 신뢰)
    # ========================================
    
    active_bet = casino.state.get_active_bet()
    pending = casino.state.get_pending_selection()
    
    status_msg = []
    
    if active_bet:
        # 진행 중인 포지션이 있음
        logger.info(f"🔄 [복구] 기존 포지션 감지: {active_bet['symbol']}")
        entry_time = active_bet.get('entry_time', 'N/A')
        entry_price = active_bet.get('entry_price', 0)
        
        status_msg.append(
            f"🔄 **[포지션 복구]**\n"
            f"Symbol: {active_bet['symbol']}\n"
            f"Entry: ${entry_price}\n"
            f"Time: {entry_time}\n"
            f"→ 자동 청산 Job 계속 작동"
        )
    elif pending:
        # 선택 대기 중이었음
        logger.warning(f"⚠️ [복구] 선택 대기 상태 감지 - 초기화됨")
        casino.state.clear_pending_selection()
        status_msg.append("🔄 이전 선택 대기 상태 초기화됨")
    else:
        # 포지션 없음 (정상)
        logger.info("✅ [정상] 포지션 없음")
        status_msg.append("💤 포지션 없음 (정상)")
    
    # ========================================
    # 🕐 JobQueue 등록
    # ========================================
    
    job_queue = application.job_queue
    
    if job_queue and chat_id:
        logger.info(f"🕐 [Scheduler] JobQueue 등록 중... (Cycle: {config.CYCLE_STRING})")
        
        # 1. 베팅 작업 (주기 간격, 10초 뒤 시작)
        job_queue.run_repeating(
            casino.job_daily_bet_callback, 
            interval=config.CYCLE_SECONDS, 
            first=10, 
            data=chat_id,
            chat_id=chat_id,
            name="daily_bet"
        )
        
        # 2. 상태 체크 작업 (1분 간격, 5초 뒤 시작)
        job_queue.run_repeating(
            casino.check_48h_exit_callback, 
            interval=60, 
            first=5, 
            data=chat_id,
            chat_id=chat_id,
            name="check_exit"
        )
        logger.info(f"✅ [Scheduler] Job 등록 완료")
        
        # ========================================
        # 📢 부팅 알림
        # ========================================
        
        boot_msg = f"🎰 **Boracay Casino System Online**\n\n💰 Balance: {free:.2f} USDT\n🕐 Cycle: {config.CYCLE_STRING}"
        
        if status_msg:
            boot_msg += "\n\n" + "\n".join(status_msg)
        
        await application.bot.send_message(
            chat_id=chat_id, 
            text=boot_msg,
            parse_mode="Markdown"
        )
        
    else:
        logger.error("❌ [Scheduler] JobQueue를 사용할 수 없거나 CHAT_ID가 없습니다.")

def main():
    global mexc, bot, casino
    
    logger.info("🎰 Boracay Casino System Initializing...")
    logger.info("==========================================")
    
    # 1. MEXC 연결
    mexc = MexcConnector()
    
    # 2. 봇 초기화 (post_init 등록)
    bot = CasinoBot(post_init=on_startup)
    
    # 3. 스케줄러 초기화
    casino = CasinoScheduler(mexc, bot)
    
    # 봇에 스케줄러 주입
    bot.scheduler = casino
    
    if bot.app:
        logger.info("🚀 시스템 가동 시작 (Press Ctrl+C to stop)")
        # 봇 실행 (JobQueue도 여기서 같이 돔)
        bot.app.run_polling()
    else:
        logger.error("❌ Telegram Bot Init Failed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n🛑 시스템 종료 (Shutdown)")

import time
import threading
import asyncio
from dotenv import load_dotenv
from exchange.mexc import MexcConnector
from utils.telegram_bot import CasinoBot
from core.scheduler_engine import CasinoScheduler

# 환경변수 로드
load_dotenv()

# 전역 변수
mexc = None
bot = None
casino = None

async def on_startup(application):
    """봇 시작 시 실행되는 초기화 로직"""
    global mexc, bot, casino
    
    print("🤖 Telegram Bot Started (Post-Init)...")
    
    # 잔고 조회
    balance, free = mexc.get_balance()
    print(f"💰 MEXC Balance: {balance} USDT (Free: {free} USDT)")
    
    # 스케줄러 스레드 시작
    def run_schedule():
        while True:
            casino.run_pending()
            time.sleep(1)
            
    t = threading.Thread(target=run_schedule, daemon=True)
    t.start()
    print("🕐 [Scheduler] 스케줄러 백그라운드 실행 중...")

    # 부팅 알림 전송
    await bot.send_message(f"🎰 Boracay Casino System Online\n💰 Balance: {free:.2f} USDT\n🕐 Scheduler Ready")

def main():
    global mexc, bot, casino
    
    print("🎰 Boracay Casino System Initializing...")
    print("==========================================")
    
    # 1. MEXC 연결
    mexc = MexcConnector()
    
    # 2. 텔레그램 봇 초기화 (post_init 훅 등록)
    bot = CasinoBot(post_init=on_startup)
    
    # 3. 스케줄러 초기화
    casino = CasinoScheduler(mexc, bot)
    
    # 봇에 스케줄러 역참조 주입
    bot.scheduler = casino
    casino.start() # 스케줄 등록

    if bot.app:
        print("🚀 System Running... (Press Ctrl+C to stop)")
        # 봇 실행 (Blocking - 메인 스레드 점유)
        bot.app.run_polling()
    else:
        print("❌ Telegram Bot Init Failed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 System Shutdown")

import os
import sys
import atexit
from datetime import datetime, timedelta
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
_lock_fp = None
_lock_path = os.path.join(os.path.dirname(__file__), ".boracay_casino_bot.lock")


def _acquire_single_instance_lock():
    """중복 실행 방지를 위한 PID lock 파일 획득."""
    global _lock_fp
    pid = os.getpid()

    def _is_process_alive(check_pid: int) -> bool:
        try:
            os.kill(check_pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # 권한이 없더라도 프로세스는 존재한다고 본다.
            return True

    def _try_create_lock_file() -> bool:
        global _lock_fp
        try:
            fd = os.open(_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            _lock_fp = os.fdopen(fd, "w")
            _lock_fp.write(str(pid))
            _lock_fp.flush()
            return True
        except FileExistsError:
            return False

    # 1차 시도
    if not _try_create_lock_file():
        # 기존 lock 파일에서 PID 읽어 살아있는지 점검
        existing_pid = None
        try:
            with open(_lock_path, "r") as f:
                raw = f.read().strip()
                if raw.isdigit():
                    existing_pid = int(raw)
        except Exception:
            pass

        if existing_pid and _is_process_alive(existing_pid):
            logger.error("❌ 이미 실행 중인 봇 인스턴스가 있습니다. 새 실행을 중단합니다.")
            return False

        # stale lock으로 판단되면 제거 후 재시도
        try:
            os.remove(_lock_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"❌ lock 파일 정리 실패: {e}")
            return False

        if not _try_create_lock_file():
            logger.error("❌ 이미 실행 중인 봇 인스턴스가 있습니다. 새 실행을 중단합니다.")
            return False

    def _release_lock():
        try:
            if _lock_fp:
                _lock_fp.close()
            if os.path.exists(_lock_path):
                os.remove(_lock_path)
        except Exception:
            pass

    atexit.register(_release_lock)
    return True


def _seconds_until_next_minute_boundary(interval_minutes: int) -> int:
    """다음 N분 경계(예: 10분이면 00/10/20...)까지 남은 초 계산."""
    if interval_minutes <= 0:
        return 0

    now = datetime.now()
    total_seconds_now = now.minute * 60 + now.second
    interval_seconds = interval_minutes * 60
    remainder = total_seconds_now % interval_seconds

    # 경계 시각에 정확히 올라왔으면 즉시 실행
    if remainder == 0 and now.microsecond == 0:
        return 0

    return interval_seconds - remainder


def _format_duration_ko(total_seconds: int) -> str:
    """초 단위를 'N일 N시간 N분 N초'로 변환."""
    seconds = max(0, int(total_seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{days}일 {hours}시간 {minutes}분 {secs}초"


def _seconds_until_first_trade_start() -> int:
    """설정된 첫 거래 시작 시각까지 남은 초 계산."""
    try:
        start_at = datetime.strptime(config.FIRST_TRADE_START_AT, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return 0
    now = datetime.now()
    if now >= start_at:
        return 0
    return int((start_at - now).total_seconds())

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
        entry_time_str = active_bet.get('entry_time', 'N/A')
        entry_price = active_bet.get('entry_price', 0)
        
        # 청산 예정 시간 체크
        try:
            entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
            exit_time = entry_time + config.CYCLE_DELTA - timedelta(seconds=config.EARLY_EXIT_SECONDS)
            now = datetime.now()
            
            if now >= exit_time:
                # 이미 청산 시간이 지났음 - 즉시 청산!
                logger.warning(f"⚠️ [복구] 청산 시간 경과 감지! (Entry: {entry_time_str}, Exit: {exit_time})")
                logger.info(f"🗑️ 즉시 청산 실행: {active_bet['symbol']}")
                
                # 현재가 조회
                current_price = mexc.get_ticker(active_bet['symbol'])
                if not current_price:
                    logger.error(f"❌ 시세 조회 실패. 진입가 기준으로 청산 처리.")
                    current_price = entry_price
                
                result = casino.state.clear_active_bet(current_price, reason="recovery_timeout")
                pnl = result['pnl_percent']
                emoji = "🎉" if pnl > 0 else "💧"
                
                status_msg.append(
                    f"⚠️ **[청산 시간 경과]**\n"
                    f"Symbol: {active_bet['symbol']}\n"
                    f"{emoji} PNL: {pnl:+.2f}%\n"
                    f"Entry: ${entry_price}\n"
                    f"Exit: ${current_price}\n"
                    f"→ 재시작 시 즉시 청산 완료"
                )
            else:
                # 아직 청산 시간 전 - 정상 복구
                remaining = exit_time - now
                remaining_minutes = int(remaining.total_seconds() / 60)
                
                status_msg.append(
                    f"🔄 **[포지션 복구]**\n"
                    f"Symbol: {active_bet['symbol']}\n"
                    f"Entry: ${entry_price}\n"
                    f"Time: {entry_time_str}\n"
                    f"⏰ 청산까지 약 {remaining_minutes}분 남음"
                )
        except Exception as e:
            logger.error(f"❌ 청산 시간 체크 실패: {e}")
            status_msg.append(
                f"🔄 **[포지션 복구]**\n"
                f"Symbol: {active_bet['symbol']}\n"
                f"Entry: ${entry_price}\n"
                f"Time: {entry_time_str}\n"
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

        # 1. 베팅 작업
        # - 시작 시각 전: FIRST_TRADE_START_AT까지 대기
        # - 시작 시각 후: 분 주기는 절대시각 경계 정렬, 시간 주기는 즉시 시작
        wait_until_start = _seconds_until_first_trade_start()
        if wait_until_start > 0:
            first_bet_in = wait_until_start
        elif config.CYCLE_MINUTES > 0:
            first_bet_in = _seconds_until_next_minute_boundary(config.CYCLE_MINUTES)
        else:
            first_bet_in = 0

        next_bet_at = datetime.now() + timedelta(seconds=first_bet_in)
        first_bet_in_human = _format_duration_ko(first_bet_in)
        logger.info(
            f"🕐 [Scheduler] 첫 베팅 실행까지 {first_bet_in_human} "
            f"(다음 실행 시각: {next_bet_at.strftime('%H:%M:%S')})"
        )

        job_queue.run_repeating(
            casino.job_daily_bet_callback, 
            interval=config.CYCLE_SECONDS, 
            first=first_bet_in,
            data=chat_id,
            chat_id=chat_id,
            name="daily_bet"
        )
        
        # 2. 상태 체크 작업 (5분 간격, 5초 뒤 시작)
        job_queue.run_repeating(
            casino.check_48h_exit_callback, 
            interval=config.CHECK_INTERVAL, 
            first=5, 
            data=chat_id,
            chat_id=chat_id,
            name="check_exit"
        )
        logger.info(f"✅ [Scheduler] Job 등록 완료")
        
        # ========================================
        # 📢 부팅 알림
        # ========================================
        
        boot_msg = (
            f"🎰 **Boracay Casino System Online**\n\n"
            f"🚦 Mode: {config.MODE_STRING}\n"
            f"💰 Balance: {free:.2f} USDT\n"
            f"🕐 Cycle: {config.CYCLE_STRING}\n"
            f"⏱️ Early Exit: {config.EARLY_EXIT_SECONDS}초\n"
            f"🛑 Stop Loss: {config.STOP_LOSS_THRESHOLD}%\n"
            f"🎯 TS Activation: +{config.TS_ACTIVATION_REWARD}%\n"
            f"📉 TS Callback: {config.TS_CALLBACK_RATE}%\n"
            f"🔍 Check Interval: {config.CHECK_INTERVAL}초\n"
            f"🕛 First Start: {config.FIRST_TRADE_START_AT}"
        )

        boot_msg += f"\n⏭️ Next Bet: {next_bet_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
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

    if not _acquire_single_instance_lock():
        sys.exit(1)
    
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

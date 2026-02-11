import schedule
import time
import asyncio
from datetime import datetime, timedelta
from core.state_manager import StateManager
from core.scanner import MarketScanner

BET_AMOUNT = 5.1  # USDT

class CasinoScheduler:
    def __init__(self, mexc, bot):
        self.mexc = mexc
        self.bot = bot
        self.state = StateManager()
        self.scanner = MarketScanner(mexc)

    def job_daily_bet(self):
        """매일 정오 실행되는 베팅 로직"""
        print(f"\n🕛 [Scheduler] 정오가 되었습니다. 베팅을 시작합니다. ({datetime.now()})")
        
        # 0. 쿨타임 체크 (가장 먼저)
        cooldown_until = self.state.get_cooldown()
        if cooldown_until:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if now_str < cooldown_until:
                msg = f"🧊 [CoolDown] 아직 쿨타임입니다.\n해제 시간: {cooldown_until}"
                print(msg)
                asyncio.run(self.bot.send_message(msg))
                return
            else:
                # 쿨타임 지났으면 초기화 (굳이 안 해도 덮어씌워지지만 명시적으로)
                self.state.state["cooldown_until"] = None
                self.state.save_state()
        
        # 1. 이미 진행 중인 베팅이 있는지 확인 (쿨타임/중복 방지)
        active = self.state.get_active_bet()
        if active:
            msg = f"⚠️ [Pass] 이미 진행 중인 게임이 있습니다.\nTarget: {active['symbol']}"
            print(msg)
            asyncio.run(self.bot.send_message(msg))
            return

        # 2. 종목 스캔
        target_symbol = self.scanner.find_target()
        if not target_symbol:
            asyncio.run(self.bot.send_message("⚠️ [Pass] 오늘 조건에 맞는 종목이 없습니다."))
            return

        # 3. 매수 실행
        # TODO: 실제 주문 기능은 주석 처리 (안전장치)
        # order = self.mexc.create_market_buy(target_symbol, BET_AMOUNT)
        
        # (Mock Order)
        current_price = self.mexc.get_ticker(target_symbol)
        if not current_price:
            print("❌ 시세 조회 실패로 매수 중단")
            return

        # 4. 상태 저장
        self.state.set_active_bet(target_symbol, current_price, BET_AMOUNT)
        
        # 5. 알림 전송
        msg = (
            f"🎰 [Jackpot Entry]\n"
            f"Symbol: {target_symbol}\n"
            f"Price: {current_price}\n"
            f"Amt: {BET_AMOUNT} USDT\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"Rule: 48시간 뒤 자동 청산"
        )
        print(msg)
        asyncio.run(self.bot.send_message(msg))

    def check_48h_exit(self):
        """매분 실행하며 48시간이 지났는지 체크"""
        active = self.state.get_active_bet()
        if not active:
            return

        # ... (기존 로직) ...

    def force_sell(self):
        """수동 매도 실행 (텔레그램 요청)"""
        active = self.state.get_active_bet()
        if not active:
            return "⚠️ 현재 진행 중인 베팅이 없습니다."

        print(f"🚨 [Force Sell] 사용자 요청으로 긴급 청산: {active['symbol']}")
        
        # 시세 조회 및 청산
        current_price = self.mexc.get_ticker(active['symbol'])
        if not current_price:
            return "❌ 시세 조회 실패. 잠시 후 다시 시도해주세요."

        # 상태 클리어 (이유: user_request)
        result = self.state.clear_active_bet(current_price, reason="user_request")
        
        pnl = result['pnl_percent']
        emoji = "🎉" if pnl > 0 else "💧"
        
        # 쿨타임 안내 추가
        cooldown_until = self.state.get_cooldown()
        
        return (
            f"✅ [매도 완료] 긴급 청산 성공!\n"
            f"{emoji} PNL: {pnl}%\n"
            f"Exit Price: {current_price}\n"
            f"🧊 쿨타임은 유지됩니다: ~{cooldown_until} 까지 진입 불가"
        )
        exit_time = entry_time + timedelta(hours=48)
        
        if datetime.now() >= exit_time:
            print(f"⏰ [Exit] 48시간 만료. 자동 청산 시도: {active['symbol']}")
            
            # TODO: 실제 매도 로직
            # result = self.mexc.create_market_sell(...)
            current_price = self.mexc.get_ticker(active['symbol'])
            
            # 상태 클리어
            result = self.state.clear_active_bet(current_price, reason="48h_timeout")
            
            pnl = result['pnl_percent']
            emoji = "🎉" if pnl > 0 else "💧"
            
            msg = (
                f"⏰ [Time's Up] 48시간 종료\n"
                f"{emoji} PNL: {pnl}%\n"
                f"Exit Price: {current_price}\n"
                f"휴식 모드로 전환합니다."
            )
            asyncio.run(self.bot.send_message(msg))

    def run_pending(self):
        schedule.run_pending()

    def start(self):
        # 매일 낮 12:00 실행
        schedule.every().day.at("12:00").do(self.job_daily_bet)
        
        # 매분 체크 (자동 청산 감시)
        schedule.every(1).minutes.do(self.check_48h_exit)
        
        print("🕐 [Scheduler] 스케줄러 가동됨 (Next 12:00 waiting...)")

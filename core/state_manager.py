import json
import os
from datetime import datetime, timedelta

STATE_FILE = "casino_state.json"

class StateManager:
    def __init__(self):
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 상태 파일 로드 실패: {e}")
        return {"active_bet": None, "history": []}

    def save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ 상태 저장 실패: {e}")

    def get_cooldown(self):
        """쿨타임 종료 시간을 반환 (없으면 None)"""
        return self.state.get("cooldown_until")

    def set_active_bet(self, symbol, entry_price, amount_usdt, entry_time=None):
        if entry_time is None:
            entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # 쿨타임 설정: 진입 시간 + 48시간
        # 실제로는 datetime 객체로 계산 후 문자열 저장
        et = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
        cooldown_until = (et + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            
        self.state["active_bet"] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "amount_usdt": amount_usdt,
            "entry_time": entry_time
        }
        self.state["cooldown_until"] = cooldown_until
        self.save_state()

    def clear_active_bet(self, exit_price, reason="48h_expired"):
        # ... (기존 로직 유지) ...
        bet = self.state.get("active_bet")
        if bet:
            bet["exit_price"] = exit_price
            bet["exit_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bet["exit_reason"] = reason
            
            # 수익률 계산 (단순화)
            if bet["entry_price"] and exit_price:
                pnl = (exit_price - bet["entry_price"]) / bet["entry_price"] * 100
                bet["pnl_percent"] = round(pnl, 2)
            else:
                bet["pnl_percent"] = 0.0

            self.state["history"].append(bet)
            self.state["active_bet"] = None
            self.save_state()
            return bet
        return None

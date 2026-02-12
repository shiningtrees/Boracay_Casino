import json
import os
from datetime import datetime, timedelta
from utils.logger import logger
import core.config as config

STATE_FILE = "casino_state.json"

class StateManager:
    def __init__(self):
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"💾 상태 파일 로드 완료: Active={data.get('active_bet') is not None}")
                    return data
            except Exception as e:
                logger.error(f"⚠️ 상태 파일 로드 실패: {e}")
        return {"active_bet": None, "history": []}

    def save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ 상태 저장 실패: {e}")

    def get_cooldown(self):
        """쿨타임 종료 시간을 반환 (없으면 None)"""
        cd = self.state.get("cooldown_until")
        if cd:
            logger.debug(f"🔍 쿨타임 조회: ~{cd}")
        return cd

    def get_active_bet(self):
        active = self.state.get("active_bet")
        if active:
            logger.debug(f"🔍 진행 중인 베팅 조회: {active['symbol']}")
        return active

    def set_active_bet(self, symbol, entry_price, amount_usdt, entry_time=None):
        if entry_time is None:
            entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # 쿨타임 설정: 진입 시간 + 설정된 주기 - 5초 (다음 주기 시작 시점엔 해제되어 있도록)
        et = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
        cooldown_until = (et + config.CYCLE_DELTA - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
            
        self.state["active_bet"] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "amount_usdt": amount_usdt,
            "entry_time": entry_time
        }
        self.state["cooldown_until"] = cooldown_until
        logger.info(f"✅ 신규 베팅 상태 저장: {symbol} (쿨타임: ~{cooldown_until})")
        self.save_state()

    def clear_active_bet(self, exit_price, reason="48h_expired"):
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
            
            logger.info(f"🧹 베팅 청산 완료: {bet['symbol']} (Reason: {reason}, PNL: {bet['pnl_percent']}%)")
            
            self.save_state()
            return bet
        return None
    
    def set_pending_selection(self, candidates, message_id=None):
        """후보 선택 대기 상태 저장"""
        self.state["pending_selection"] = {
            "candidates": candidates,
            "message_id": message_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info(f"⏳ 선택 대기 상태 저장: {len(candidates)}개 후보")
        self.save_state()
    
    def get_pending_selection(self):
        """후보 선택 대기 상태 조회"""
        return self.state.get("pending_selection")
    
    def clear_pending_selection(self):
        """후보 선택 대기 상태 제거"""
        if self.state.get("pending_selection"):
            logger.info("🧹 선택 대기 상태 제거")
            self.state["pending_selection"] = None
            self.save_state()

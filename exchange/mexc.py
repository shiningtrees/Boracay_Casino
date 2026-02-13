import ccxt
import os
from dotenv import load_dotenv
from utils.logger import logger

load_dotenv()

class MexcConnector:
    def __init__(self):
        self.api_key = os.getenv("MEXC_ACCESS_KEY")
        self.secret_key = os.getenv("MEXC_SECRET_KEY")
        
        if not self.api_key or not self.secret_key:
            logger.warning("⚠️ [MEXC] API Key or Secret is missing in .env")
        
        self.exchange = ccxt.mexc({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'  # 현물 기준 (필요시 future로 변경)
            }
        })
        
    def get_balance(self):
        """USDT 잔고 조회"""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance['total'].get('USDT', 0)
            free_usdt = balance['free'].get('USDT', 0)
            return usdt, free_usdt
        except Exception as e:
            logger.error(f"❌ [MEXC] 잔고 조회 실패: {e}")
            return 0, 0
    
    def get_holdings(self, exclude=['USDT']):
        """USDT 외 보유 코인 조회 (포지션 감지용)"""
        try:
            balance = self.exchange.fetch_balance()
            holdings = []
            
            for currency, amount in balance['total'].items():
                if currency in exclude:
                    continue
                
                # 잔액이 있는 코인만 (먼지 제외: 0.0001 이상)
                if amount and amount > 0.0001:
                    holdings.append({
                        'currency': currency,
                        'amount': amount,
                        'free': balance['free'].get(currency, 0),
                        'symbol': f"{currency}/USDT"
                    })
            
            return holdings
        except Exception as e:
            logger.error(f"❌ [MEXC] 보유 코인 조회 실패: {e}")
            return []

    def get_ticker(self, symbol):
        """현재가 조회 (예: BTC/USDT)"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"❌ [MEXC] 시세 조회 실패 ({symbol}): {e}")
            return None

    def create_market_buy(self, symbol, amount_usdt):
        """시장가 매수 (금액 기준)"""
        try:
            # MEXC spot은 시장가 매수 시 base 수량을 받는 경우가 많아, 금액->수량으로 변환
            ticker = self.exchange.fetch_ticker(symbol)
            last_price = ticker.get('last')
            if not last_price or last_price <= 0:
                logger.error(f"❌ [MEXC] 매수 실패 ({symbol}): 유효한 현재가 없음")
                return None

            amount_base = float(amount_usdt) / float(last_price)
            amount_base = float(self.exchange.amount_to_precision(symbol, amount_base))
            if amount_base <= 0:
                logger.error(f"❌ [MEXC] 매수 실패 ({symbol}): 계산된 수량이 0")
                return None

            order = self.exchange.create_order(
                symbol, 
                'market', 
                'buy', 
                amount_base,
            )
            return order
        except Exception as e:
            logger.error(f"❌ [MEXC] 매수 실패 ({symbol}): {e}")
            return None

    def create_market_sell(self, symbol, amount=None):
        """시장가 매도 (기본: 해당 코인 free 전량)"""
        try:
            base_currency = symbol.split('/')[0]

            if amount is None:
                balance = self.exchange.fetch_balance()
                amount = balance['free'].get(base_currency, 0)

            amount = float(amount)
            if amount <= 0:
                logger.error(f"❌ [MEXC] 매도 실패 ({symbol}): 매도 가능 수량 없음")
                return None

            amount = float(self.exchange.amount_to_precision(symbol, amount))
            if amount <= 0:
                logger.error(f"❌ [MEXC] 매도 실패 ({symbol}): 정밀도 반영 후 수량 0")
                return None

            order = self.exchange.create_order(
                symbol,
                'market',
                'sell',
                amount,
            )
            return order
        except Exception as e:
            logger.error(f"❌ [MEXC] 매도 실패 ({symbol}): {e}")
            return None

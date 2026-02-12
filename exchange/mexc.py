import ccxt
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class MexcConnector:
    def __init__(self):
        self.api_key = os.getenv("MEXC_ACCESS_KEY")
        self.secret_key = os.getenv("MEXC_SECRET_KEY")
        
        if not self.api_key or not self.secret_key:
            print("⚠️ [MEXC] API Key or Secret is missing in .env")
        
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
            print(f"❌ [MEXC] 잔고 조회 실패: {e}")
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
            print(f"❌ [MEXC] 보유 코인 조회 실패: {e}")
            return []

    def get_ticker(self, symbol):
        """현재가 조회 (예: BTC/USDT)"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"❌ [MEXC] 시세 조회 실패 ({symbol}): {e}")
            return None

    def create_market_buy(self, symbol, amount_usdt):
        """시장가 매수 (금액 기준)"""
        try:
            # MEXC는 시장가 매수 시 'quoteOrderQty'를 지원하는지 확인 필요
            # 일반적으로 create_order 사용
            order = self.exchange.create_order(
                symbol, 
                'market', 
                'buy', 
                amount_usdt, # amount (coin 개수)가 아니라 cost(USDT)일 수 있음. 확인 필요.
                # CCXT MEXC spot market buy usually takes amount in base currency or quoteOrderQty
                # 안전하게는 create_market_buy_order_with_cost (if supported) or logic to calc amount
                # 여기서는 일단 quoteOrderQty 파라미터를 시도
            )
            return order
        except Exception as e:
            print(f"❌ [MEXC] 매수 실패 ({symbol}): {e}")
            return None

    # TODO: 안전한 매수를 위한 코인 개수 계산 로직 추가 필요

import random

class MarketScanner:
    def __init__(self, mexc_connector):
        self.mexc = mexc_connector

    def find_target(self):
        """
        [Phase 1 Simple Logic]
        거래량 상위 & 변동성 좋은 종목을 찾아 리턴.
        (현재는 API 과부하 방지를 위해 예시 로직으로 구현)
        """
        print("🔍 [Scanner] 종목 스캔 중...")
        
        try:
            # 1. MEXC 전체 티커 조회
            tickers = self.mexc.exchange.fetch_tickers()
            
            # 2. 필터링 (USDT 마켓만)
            candidates = []
            for symbol, data in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                
                # 거래대금(quoteVolume) 100만불 이상
                if data['quoteVolume'] is None or data['quoteVolume'] < 1_000_000:
                    continue
                
                # 24시간 변동률 (percentage) 5% ~ 30% 사이 (너무 과열된 건 제외)
                change = data.get('percentage')
                if change is None:
                    continue
                    
                if 5.0 <= change <= 30.0:
                    candidates.append({
                        'symbol': symbol,
                        'change': change,
                        'volume': data['quoteVolume']
                    })
            
            if not candidates:
                print("⚠️ 조건에 맞는 종목 없음.")
                return None
                
            # 3. 거래대금 순 정렬 후 상위 5개 중 랜덤 픽 (운빨 요소 추가)
            candidates.sort(key=lambda x: x['volume'], reverse=True)
            top_picks = candidates[:5]
            
            target = random.choice(top_picks)
            print(f"🎯 [Scanner] Target Found: {target['symbol']} (+{target['change']}%)")
            return target['symbol']

        except Exception as e:
            print(f"❌ [Scanner] 스캔 중 오류: {e}")
            return None

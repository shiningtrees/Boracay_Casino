import random
from utils.logger import logger

class MarketScanner:
    def __init__(self, mexc_connector):
        self.mexc = mexc_connector
        self._last_candidates = []  # 마지막 스캔 결과 캐싱

    def find_target(self):
        """
        [공격적 버전] 
        높은 변동성 + 거래량 기반 종목 선정
        - 변동률: 15% ~ 40%
        - 거래대금: 100만불 이상
        - 모멘텀 스코어 기반 상위 종목 중 랜덤
        """
        print("🔍 [Scanner] 공격적 종목 스캔 중...")
        
        try:
            # 1. MEXC 전체 티커 조회
            tickers = self.mexc.exchange.fetch_tickers()
            
            # 2. 필터링 (공격적 조건)
            candidates = []
            for symbol, data in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                
                # 거래대금(quoteVolume) 100만불 이상 (유동성 확보)
                if data['quoteVolume'] is None or data['quoteVolume'] < 1_000_000:
                    continue
                
                # 24시간 변동률 15% ~ 40% (공격적 범위)
                change = data.get('percentage')
                if change is None:
                    continue
                    
                if 15.0 <= change <= 40.0:
                    # 모멘텀 스코어 계산 (변동률 * 거래량 가중치)
                    # 거래량이 많고 변동률도 높을수록 높은 점수
                    volume_weight = data['quoteVolume'] / 1_000_000  # 100만불 기준 정규화
                    momentum_score = change * (1 + volume_weight * 0.1)
                    
                    candidates.append({
                        'symbol': symbol,
                        'change': change,
                        'volume': data['quoteVolume'],
                        'score': momentum_score
                    })
            
            if not candidates:
                print("⚠️ 공격적 조건에 맞는 종목 없음. (15~40% 변동 + 100만불)")
                # Fallback: 조건 완화
                print("🔄 [Scanner] 조건 완화 중... (10~40%)")
                for symbol, data in tickers.items():
                    if not symbol.endswith('/USDT'):
                        continue
                    if data['quoteVolume'] is None or data['quoteVolume'] < 500_000:
                        continue
                    change = data.get('percentage')
                    if change and 10.0 <= change <= 40.0:
                        volume_weight = data['quoteVolume'] / 1_000_000
                        momentum_score = change * (1 + volume_weight * 0.1)
                        candidates.append({
                            'symbol': symbol,
                            'change': change,
                            'volume': data['quoteVolume'],
                            'score': momentum_score
                        })
                
                if not candidates:
                    print("❌ [Scanner] 조건 완화 후에도 종목 없음.")
                    return None
                
            # 3. 모멘텀 스코어 순 정렬 후 상위 10개 중 랜덤 픽
            candidates.sort(key=lambda x: x['score'], reverse=True)
            top_picks = candidates[:10]
            
            target = random.choice(top_picks)
            print(f"🎯 [Scanner] 공격적 타겟 선정!")
            print(f"   Symbol: {target['symbol']}")
            print(f"   Change: +{target['change']:.2f}%")
            print(f"   Volume: ${target['volume']:,.0f}")
            print(f"   Score: {target['score']:.2f}")
            
            return target['symbol']

        except Exception as e:
            print(f"❌ [Scanner] 스캔 중 오류: {e}")
            return None
    
    def find_candidates(self, count=3):
        """
        [게임 모드] 복수 후보 선정
        사용자가 선택할 수 있도록 count개의 후보를 반환
        """
        logger.info(f"🎯 [Scanner] {count}개 후보 코인 스캔 중...")
        
        try:
            # 1. MEXC 전체 티커 조회
            tickers = self.mexc.exchange.fetch_tickers()
            
            # 2. 필터링 (공격적 조건)
            candidates = []
            for symbol, data in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                
                if data['quoteVolume'] is None or data['quoteVolume'] < 1_000_000:
                    continue
                
                change = data.get('percentage')
                if change is None:
                    continue
                    
                if 15.0 <= change <= 40.0:
                    volume_weight = data['quoteVolume'] / 1_000_000
                    momentum_score = change * (1 + volume_weight * 0.1)
                    
                    candidates.append({
                        'symbol': symbol,
                        'change': change,
                        'volume': data['quoteVolume'],
                        'score': momentum_score,
                        'last_price': data.get('last', 0)
                    })
            
            # Fallback 처리
            if not candidates:
                logger.warning("⚠️ 공격적 조건에 맞는 종목 없음. 조건 완화 중...")
                for symbol, data in tickers.items():
                    if not symbol.endswith('/USDT'):
                        continue
                    if data['quoteVolume'] is None or data['quoteVolume'] < 500_000:
                        continue
                    change = data.get('percentage')
                    if change and 10.0 <= change <= 40.0:
                        volume_weight = data['quoteVolume'] / 1_000_000
                        momentum_score = change * (1 + volume_weight * 0.1)
                        candidates.append({
                            'symbol': symbol,
                            'change': change,
                            'volume': data['quoteVolume'],
                            'score': momentum_score,
                            'last_price': data.get('last', 0)
                        })
                
                if not candidates:
                    logger.error("❌ [Scanner] 조건 완화 후에도 종목 없음.")
                    return []
            
            # 3. 스코어 순 정렬 후 상위에서 랜덤하게 count개 선택
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # 상위 20개 중에서 랜덤하게 count개 픽 (다양성 확보)
            pool_size = min(20, len(candidates))
            pool = candidates[:pool_size]
            
            if len(pool) < count:
                logger.warning(f"⚠️ 요청한 {count}개보다 적은 {len(pool)}개만 발견됨")
                selected = pool
            else:
                selected = random.sample(pool, count)
            
            # 캐싱
            self._last_candidates = selected
            
            logger.info(f"✅ [Scanner] {len(selected)}개 후보 선정 완료:")
            for idx, c in enumerate(selected, 1):
                logger.info(f"   {idx}. {c['symbol']} (+{c['change']:.2f}%, Score: {c['score']:.2f})")
            
            return selected

        except Exception as e:
            logger.error(f"❌ [Scanner] 후보 스캔 중 오류: {e}")
            return []

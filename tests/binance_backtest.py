"""
🎰 Boracay Casino Backtest Engine - Binance Version

Binance API를 사용하여 장기 백테스트 수행.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json
import random


class BacktestConfig:
    """백테스트 설정"""
    # 자산 설정
    INITIAL_BALANCE = 100.0
    BET_AMOUNT = 5.1
    
    # 전략 설정 (실전 로직과 동일)
    STOP_LOSS_THRESHOLD = -25.0
    TS_ACTIVATION_REWARD = 25.0
    TS_CALLBACK_RATE = 10.0
    
    # 거래 비용
    TRADING_FEE_PERCENT = 0.3
    
    # 데이터 설정
    TIMEFRAME = '5m'
    
    # 테스트할 주기들 (시간 단위)
    TEST_CYCLES = [48, 72, 96]


class Position:
    """포지션 상태"""
    def __init__(self, symbol: str, entry_price: float, amount_usdt: float, entry_time: datetime):
        self.symbol = symbol
        self.entry_price = entry_price
        self.amount_usdt = amount_usdt
        self.entry_time = entry_time
        
        # 트레일링 스탑 상태
        self.is_ts_active = False
        self.peak_price = None
        
    def activate_trailing_stop(self, peak_price: float):
        self.is_ts_active = True
        self.peak_price = peak_price
        
    def update_peak_price(self, new_peak: float):
        if self.is_ts_active and new_peak > self.peak_price:
            self.peak_price = new_peak
            
    def get_pnl_percent(self, current_price: float) -> float:
        return ((current_price - self.entry_price) / self.entry_price) * 100


class Trade:
    """거래 기록"""
    def __init__(self, symbol: str, entry_price: float, exit_price: float,
                 entry_time: datetime, exit_time: datetime, 
                 amount_usdt: float, pnl_percent: float, exit_reason: str):
        self.symbol = symbol
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.amount_usdt = amount_usdt
        self.pnl_percent = pnl_percent
        self.exit_reason = exit_reason
        
        self.net_pnl_usdt = amount_usdt * (pnl_percent / 100) * (1 - BacktestConfig.TRADING_FEE_PERCENT / 100)
        
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': self.exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_hours': (self.exit_time - self.entry_time).total_seconds() / 3600,
            'amount_usdt': self.amount_usdt,
            'pnl_percent': round(self.pnl_percent, 2),
            'net_pnl_usdt': round(self.net_pnl_usdt, 2),
            'exit_reason': self.exit_reason
        }


class BinanceBacktestEngine:
    """Binance 백테스트 엔진"""
    
    def __init__(self, cycle_hours: int, use_scanner: bool = False):
        self.cycle_hours = cycle_hours
        self.use_scanner = use_scanner
        self.balance = BacktestConfig.INITIAL_BALANCE
        self.peak_balance = BacktestConfig.INITIAL_BALANCE
        self.position: Position = None
        self.trades: List[Trade] = []
        self.bankruptcy_point = None
        
        # Binance 연결
        self.exchange = ccxt.binance({'enableRateLimit': True})
        
        # 공통 코인 목록 (MEXC와 Binance 둘 다 있는 코인)
        self.common_coins = None
        
    def load_common_coins(self):
        """MEXC와 Binance 공통 코인 로드"""
        if self.common_coins is not None:
            return
        
        print("📋 공통 코인 목록 로드 중...")
        try:
            mexc = ccxt.mexc()
            mexc_markets = mexc.load_markets()
            binance_markets = self.exchange.load_markets()
            
            mexc_usdt = set([s for s in mexc_markets.keys() if s.endswith('/USDT') and mexc_markets[s]['active']])
            binance_usdt = set([s for s in binance_markets.keys() if s.endswith('/USDT') and binance_markets[s]['active']])
            
            self.common_coins = list(mexc_usdt & binance_usdt)
            print(f"✅ 공통 코인: {len(self.common_coins)}개")
            
        except Exception as e:
            print(f"❌ 공통 코인 로드 실패: {e}")
            self.common_coins = []
    
    def scan_random_coin(self) -> str:
        """스캐너로 랜덤 코인 선정 (공통 코인 중에서)"""
        if not self.common_coins:
            self.load_common_coins()
        
        if not self.common_coins:
            return None
        
        try:
            # 전체 티커 조회
            tickers = self.exchange.fetch_tickers()
            
            # 필터링 (공통 코인 중에서만)
            candidates = []
            for symbol in self.common_coins:
                if symbol not in tickers:
                    continue
                
                data = tickers[symbol]
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
                        'score': momentum_score
                    })
            
            # Fallback
            if not candidates:
                for symbol in self.common_coins:
                    if symbol not in tickers:
                        continue
                    data = tickers[symbol]
                    if data['quoteVolume'] is None or data['quoteVolume'] < 500_000:
                        continue
                    change = data.get('percentage')
                    if change and 10.0 <= change <= 40.0:
                        volume_weight = data['quoteVolume'] / 1_000_000
                        momentum_score = change * (1 + volume_weight * 0.1)
                        candidates.append({
                            'symbol': symbol,
                            'score': momentum_score
                        })
            
            if not candidates:
                # 최후의 수단: 공통 코인 중 랜덤
                return random.choice(self.common_coins)
            
            # 상위 20개 중 랜덤 선택
            candidates.sort(key=lambda x: x['score'], reverse=True)
            pool = candidates[:min(20, len(candidates))]
            
            selected = random.choice(pool)
            return selected['symbol']
            
        except Exception as e:
            print(f"  ⚠️ 스캐너 에러: {e}")
            # 에러 시 공통 코인 중 랜덤
            return random.choice(self.common_coins) if self.common_coins else None
    
    def fetch_historical_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Binance에서 과거 5분봉 데이터 조회"""
        since = self.exchange.parse8601(f"{start_date}T00:00:00Z")
        end = self.exchange.parse8601(f"{end_date}T23:59:59Z")
        
        all_candles = []
        current = since
        
        print(f"  📊 [{symbol}] 데이터 다운로드 중...")
        
        error_count = 0
        max_errors = 3
        
        while current < end:
            try:
                candles = self.exchange.fetch_ohlcv(symbol, BacktestConfig.TIMEFRAME, since=current, limit=1000)
                
                if not candles:
                    break
                
                all_candles.extend(candles)
                current = candles[-1][0] + 1
                
                if len(all_candles) % 10000 == 0:
                    print(f"    - {len(all_candles)} candles...")
                
                error_count = 0
                    
            except Exception as e:
                error_count += 1
                if error_count >= max_errors:
                    print(f"    ⚠️ 최대 에러 도달. 수집된 데이터로 진행: {len(all_candles)} candles")
                    break
                import time
                time.sleep(1)
        
        if not all_candles:
            raise ValueError(f"데이터 없음: {symbol}")
        
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
        
        print(f"  ✅ {len(df)} candles")
        
        if len(df) == 0:
            raise ValueError(f"날짜 범위 내 데이터 없음")
        
        return df
    
    def check_exit_conditions(self, candle: pd.Series) -> Tuple[bool, str]:
        """청산 조건 체크"""
        if not self.position:
            return False, None
        
        high = candle['high']
        low = candle['low']
        current_time = candle['datetime']
        
        # 1. 손절
        pnl_at_low = self.position.get_pnl_percent(low)
        if pnl_at_low <= BacktestConfig.STOP_LOSS_THRESHOLD:
            return True, 'stop_loss'
        
        # 2. 트레일링 활성화
        pnl_at_high = self.position.get_pnl_percent(high)
        if not self.position.is_ts_active and pnl_at_high >= BacktestConfig.TS_ACTIVATION_REWARD:
            self.position.activate_trailing_stop(high)
        
        # 3. 트레일링 익절
        if self.position.is_ts_active:
            self.position.update_peak_price(high)
            callback_threshold = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
            if low <= callback_threshold:
                return True, 'trailing_stop'
        
        # 4. 타임아웃
        elapsed = current_time - self.position.entry_time
        if elapsed >= timedelta(hours=self.cycle_hours):
            return True, 'timeout'
        
        return False, None
    
    def execute_entry(self, symbol: str, entry_price: float, entry_time: datetime):
        self.position = Position(symbol, entry_price, BacktestConfig.BET_AMOUNT, entry_time)
    
    def execute_exit(self, exit_price: float, exit_time: datetime, exit_reason: str):
        if not self.position:
            return
        
        pnl_percent = self.position.get_pnl_percent(exit_price)
        
        trade = Trade(
            symbol=self.position.symbol,
            entry_price=self.position.entry_price,
            exit_price=exit_price,
            entry_time=self.position.entry_time,
            exit_time=exit_time,
            amount_usdt=self.position.amount_usdt,
            pnl_percent=pnl_percent,
            exit_reason=exit_reason
        )
        
        self.balance += trade.net_pnl_usdt
        
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        if self.balance < BacktestConfig.BET_AMOUNT and self.bankruptcy_point is None:
            self.bankruptcy_point = {
                'time': exit_time,
                'balance': self.balance,
                'trade_count': len(self.trades) + 1
            }
        
        self.trades.append(trade)
        self.position = None
    
    def run_simulation_single_symbol(self, symbol: str, start_date: str, end_date: str):
        """단일 심볼 시뮬레이션"""
        df = self.fetch_historical_data(symbol, start_date, end_date)
        
        for idx, candle in df.iterrows():
            current_time = candle['datetime']
            
            if self.position:
                should_exit, exit_reason = self.check_exit_conditions(candle)
                
                if should_exit:
                    if exit_reason == 'stop_loss':
                        exit_price = candle['low']
                    elif exit_reason == 'trailing_stop':
                        exit_price = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
                    else:
                        exit_price = candle['close']
                    
                    self.execute_exit(exit_price, current_time, exit_reason)
            
            else:
                remaining_time = df['datetime'].iloc[-1] - current_time
                if remaining_time >= timedelta(hours=self.cycle_hours):
                    self.execute_entry(symbol, candle['close'], current_time)
        
        if self.position:
            last_candle = df.iloc[-1]
            self.execute_exit(last_candle['close'], last_candle['datetime'], 'simulation_end')
    
    def run_simulation_scanner(self, start_date: str, end_date: str):
        """스캐너 모드 시뮬레이션"""
        self.load_common_coins()
        
        current_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        print(f"🎲 스캐너 시뮬레이션 시작 (공통 코인 풀)")
        
        cycle_count = 0
        
        while current_time < end_time:
            cycle_count += 1
            
            remaining = (end_time - current_time).total_seconds() / 3600
            if remaining < self.cycle_hours:
                break
            
            # 코인 선정
            symbol = self.scan_random_coin()
            if not symbol:
                print(f"  Cycle {cycle_count}: 코인 선정 실패")
                current_time += timedelta(hours=self.cycle_hours)
                continue
            
            print(f"  Cycle {cycle_count}: {symbol}")
            
            # 주기 데이터 조회 및 시뮬레이션
            cycle_end = current_time + timedelta(hours=self.cycle_hours)
            
            try:
                df = self.fetch_historical_data(symbol, 
                                               current_time.strftime("%Y-%m-%d"),
                                               cycle_end.strftime("%Y-%m-%d"))
                
                # 진입
                entry_candle = df.iloc[0]
                self.execute_entry(symbol, entry_candle['close'], entry_candle['datetime'])
                
                # 주기 동안 체크
                for idx, candle in df.iterrows():
                    if not self.position:
                        break
                    
                    should_exit, exit_reason = self.check_exit_conditions(candle)
                    
                    if should_exit:
                        if exit_reason == 'stop_loss':
                            exit_price = candle['low']
                        elif exit_reason == 'trailing_stop':
                            exit_price = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
                        else:
                            exit_price = candle['close']
                        
                        self.execute_exit(exit_price, candle['datetime'], exit_reason)
                        print(f"    → {exit_reason} @ ${exit_price:.2f}, PNL: {self.trades[-1].pnl_percent:+.2f}%")
                        break
                
                # 타임아웃
                if self.position:
                    last_candle = df.iloc[-1]
                    self.execute_exit(last_candle['close'], last_candle['datetime'], 'timeout')
                    print(f"    → timeout @ ${last_candle['close']:.2f}, PNL: {self.trades[-1].pnl_percent:+.2f}%")
                
            except Exception as e:
                print(f"    ⚠️ 에러: {e}")
            
            current_time = cycle_end
        
        print(f"\n✅ 시뮬레이션 완료: {cycle_count} cycles, {len(self.trades)} trades")
    
    def run_simulation(self, symbol: str, start_date: str, end_date: str):
        """시뮬레이션 실행"""
        print(f"\n{'='*60}")
        if self.use_scanner:
            print(f"🎰 Binance 백테스트 (스캐너 모드, {self.cycle_hours}h)")
        else:
            print(f"🎰 Binance 백테스트: {symbol} ({self.cycle_hours}h)")
        print(f"{'='*60}")
        
        if self.use_scanner:
            self.run_simulation_scanner(start_date, end_date)
        else:
            self.run_simulation_single_symbol(symbol, start_date, end_date)
        
        print(f"  최종 잔고: {self.balance:.2f} USDT")
    
    def generate_report(self) -> dict:
        """리포트 생성"""
        if not self.trades:
            return {'error': '거래 없음'}
        
        winning_trades = [t for t in self.trades if t.pnl_percent > 0]
        losing_trades = [t for t in self.trades if t.pnl_percent <= 0]
        
        exit_reasons = {}
        for trade in self.trades:
            reason = trade.exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        max_jackpot = max(self.trades, key=lambda t: t.pnl_percent)
        
        survival_days = None
        if self.trades:
            first_trade = self.trades[0]
            last_trade = self.trades[-1]
            survival_days = (last_trade.exit_time - first_trade.entry_time).days
        
        return {
            'cycle_hours': self.cycle_hours,
            'initial_balance': BacktestConfig.INITIAL_BALANCE,
            'final_balance': round(self.balance, 2),
            'peak_balance': round(self.peak_balance, 2),
            'total_pnl': round(self.balance - BacktestConfig.INITIAL_BALANCE, 2),
            'total_pnl_percent': round((self.balance - BacktestConfig.INITIAL_BALANCE) / BacktestConfig.INITIAL_BALANCE * 100, 2),
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(len(winning_trades) / len(self.trades) * 100, 2) if self.trades else 0,
            'exit_reasons': exit_reasons,
            'avg_pnl_percent': round(sum(t.pnl_percent for t in self.trades) / len(self.trades), 2),
            'avg_win_percent': round(sum(t.pnl_percent for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
            'avg_loss_percent': round(sum(t.pnl_percent for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
            'max_jackpot': {
                'symbol': max_jackpot.symbol,
                'pnl_percent': round(max_jackpot.pnl_percent, 2),
                'exit_reason': max_jackpot.exit_reason,
                'entry_time': max_jackpot.entry_time.strftime('%Y-%m-%d %H:%M')
            },
            'survival_days': survival_days,
            'bankruptcy_point': self.bankruptcy_point,
            'trades': [t.to_dict() for t in self.trades]
        }


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 4:
        print("사용법: python binance_backtest.py <SYMBOL|SCANNER> <START_DATE> <END_DATE> [CYCLES]")
        print("예: python binance_backtest.py SCANNER 2025-01-01 2026-02-14 48,72,96")
        sys.exit(1)
    
    symbol = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    cycles = [int(c) for c in sys.argv[4].split(',')] if len(sys.argv) > 4 else [48, 72, 96]
    
    use_scanner = symbol.upper() == 'SCANNER'
    
    BacktestConfig.TEST_CYCLES = cycles
    
    results = {}
    
    for cycle_hours in BacktestConfig.TEST_CYCLES:
        engine = BinanceBacktestEngine(cycle_hours, use_scanner=use_scanner)
        engine.run_simulation(symbol, start_date, end_date)
        results[f"{cycle_hours}h"] = engine.generate_report()
    
    # 결과 저장
    output_file = f"binance_backtest_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'exchange': 'Binance',
            'mode': 'scanner' if use_scanner else 'single_symbol',
            'symbol': symbol,
            'period': f"{start_date} ~ {end_date}",
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 결과 저장: {output_file}")
    
    # 요약
    print(f"\n{'='*60}")
    print("📊 백테스트 요약")
    print(f"{'='*60}")
    for cycle, result in results.items():
        print(f"\n{cycle}:")
        print(f"  잔고: {result['final_balance']} USDT ({result['total_pnl_percent']:+.2f}%)")
        print(f"  거래: {result['total_trades']}회 (승률: {result['win_rate']}%)")
        print(f"  청산: {result['exit_reasons']}")

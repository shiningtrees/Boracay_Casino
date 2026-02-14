"""
🎰 Boracay Casino Backtest Engine

실전 트레일링 스탑 전략과 100% 동기화된 백테스트 엔진.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json


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
    TRADING_FEE_PERCENT = 0.3  # 진입/청산 각 0.15%, 총 0.3%
    
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
        """트레일링 스탑 활성화"""
        self.is_ts_active = True
        self.peak_price = peak_price
        
    def update_peak_price(self, new_peak: float):
        """최고가 갱신"""
        if self.is_ts_active and new_peak > self.peak_price:
            self.peak_price = new_peak
            
    def get_pnl_percent(self, current_price: float) -> float:
        """현재 수익률 계산"""
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
        
        # 거래 비용 적용한 실제 손익
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


class BacktestEngine:
    """백테스트 엔진"""
    
    def __init__(self, cycle_hours: int, use_scanner: bool = False):
        self.cycle_hours = cycle_hours
        self.use_scanner = use_scanner  # 스캐너 사용 여부
        self.balance = BacktestConfig.INITIAL_BALANCE
        self.peak_balance = BacktestConfig.INITIAL_BALANCE
        self.position: Position = None
        self.trades: List[Trade] = []
        self.bankruptcy_point = None
        
        # 스캐너 사용 시 MEXC 커넥터 초기화
        if use_scanner:
            import ccxt
            self.exchange = ccxt.mexc({'enableRateLimit': True})
        else:
            self.exchange = None
        
    def scan_random_coin(self) -> str:
        """스캐너로 랜덤 코인 선정 (실전과 동일)"""
        try:
            # 1. 전체 티커 조회
            tickers = self.exchange.fetch_tickers()
            
            # 2. 필터링 (scanner.py와 동일한 로직)
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
                        'score': momentum_score
                    })
            
            # Fallback
            if not candidates:
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
                            'score': momentum_score
                        })
            
            if not candidates:
                return None
            
            # 3. 상위 20개 중 랜덤 선택
            candidates.sort(key=lambda x: x['score'], reverse=True)
            pool = candidates[:min(20, len(candidates))]
            
            import random
            selected = random.choice(pool)
            return selected['symbol']
            
        except Exception as e:
            print(f"❌ 스캐너 실패: {e}")
            return None
    
    def fetch_historical_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """MEXC에서 과거 5분봉 데이터 조회"""
        exchange = ccxt.mexc({'enableRateLimit': True})
        
        since = exchange.parse8601(f"{start_date}T00:00:00Z")
        end = exchange.parse8601(f"{end_date}T23:59:59Z")
        
        all_candles = []
        current = since
        
        print(f"📊 [{symbol}] 데이터 다운로드 중... ({start_date} ~ {end_date})")
        print(f"  - Since timestamp: {since}")
        print(f"  - End timestamp: {end}")
        
        error_count = 0
        max_errors = 3
        
        while current < end:
            try:
                candles = exchange.fetch_ohlcv(symbol, BacktestConfig.TIMEFRAME, since=current, limit=1000)
                
                if not candles:
                    print(f"  - 더 이상 데이터 없음 (current: {current})")
                    break
                
                all_candles.extend(candles)
                current = candles[-1][0] + 1
                
                if len(all_candles) % 5000 == 0:
                    print(f"  - {len(all_candles)} candles...")
                
                # 에러 카운트 리셋
                error_count = 0
                    
            except Exception as e:
                error_count += 1
                print(f"❌ 데이터 조회 실패 ({error_count}/{max_errors}): {e}")
                
                if error_count >= max_errors:
                    print(f"⚠️ 최대 에러 횟수 도달. 수집된 데이터로 진행...")
                    break
                
                # 재시도 전 대기
                import time
                time.sleep(2)
        
        if not all_candles:
            raise ValueError(f"데이터 조회 실패: {symbol}. 수집된 캔들 없음.")
        
        print(f"  - 총 수집: {len(all_candles)} candles")
        
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 날짜 필터링
        df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
        
        print(f"✅ [{symbol}] {len(df)} candles 로드 완료 (날짜 필터링 후)")
        
        if len(df) == 0:
            raise ValueError(f"날짜 범위 내 데이터 없음: {start_date} ~ {end_date}")
        
        return df
    
    def check_exit_conditions(self, candle: pd.Series) -> Tuple[bool, str]:
        """청산 조건 체크 (High/Low 기준)"""
        if not self.position:
            return False, None
        
        high = candle['high']
        low = candle['low']
        close = candle['close']
        current_time = candle['datetime']
        
        # 1. 손절 체크 (Low 기준)
        pnl_at_low = self.position.get_pnl_percent(low)
        if pnl_at_low <= BacktestConfig.STOP_LOSS_THRESHOLD:
            return True, 'stop_loss'
        
        # 2. 트레일링 활성화 체크 (High 기준)
        pnl_at_high = self.position.get_pnl_percent(high)
        if not self.position.is_ts_active and pnl_at_high >= BacktestConfig.TS_ACTIVATION_REWARD:
            self.position.activate_trailing_stop(high)
        
        # 3. 트레일링 스탑 로직
        if self.position.is_ts_active:
            # 최고가 갱신
            self.position.update_peak_price(high)
            
            # 익절 조건: Low가 peak 대비 10% 하락
            callback_threshold = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
            if low <= callback_threshold:
                return True, 'trailing_stop'
        
        # 4. 타임아웃 체크
        elapsed = current_time - self.position.entry_time
        if elapsed >= timedelta(hours=self.cycle_hours):
            return True, 'timeout'
        
        return False, None
    
    def execute_entry(self, symbol: str, entry_price: float, entry_time: datetime) -> bool:
        """진입 실행"""
        if self.balance < BacktestConfig.BET_AMOUNT:
            # 잔고 부족해도 계속 진행 (마이너스 잔고 허용)
            pass
        
        self.position = Position(symbol, entry_price, BacktestConfig.BET_AMOUNT, entry_time)
        return True
    
    def execute_exit(self, exit_price: float, exit_time: datetime, exit_reason: str):
        """청산 실행"""
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
        
        # 잔고 업데이트
        self.balance += trade.net_pnl_usdt
        
        # 최고 잔고 갱신
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        # 파산 지점 기록 (최초 1회만)
        if self.balance < BacktestConfig.BET_AMOUNT and self.bankruptcy_point is None:
            self.bankruptcy_point = {
                'time': exit_time,
                'balance': self.balance,
                'trade_count': len(self.trades) + 1
            }
        
        self.trades.append(trade)
        self.position = None
    
    def run_simulation(self, symbol: str, start_date: str, end_date: str):
        """시뮬레이션 실행"""
        print(f"\n{'='*60}")
        if self.use_scanner:
            print(f"🎰 백테스트 시작: 스캐너 모드 (주기: {self.cycle_hours}시간)")
            print(f"   매 사이클마다 상위 20개 중 랜덤 선택")
        else:
            print(f"🎰 백테스트 시작: {symbol} (주기: {self.cycle_hours}시간)")
        print(f"{'='*60}")
        
        # 스캐너 모드가 아니면 기존 방식 (단일 심볼 데이터 로드)
        if not self.use_scanner:
            df = self.fetch_historical_data(symbol, start_date, end_date)
            self._run_simulation_with_data(symbol, df)
        else:
            # 스캐너 모드: 매 사이클마다 새 코인 선정
            self._run_simulation_with_scanner(start_date, end_date)
    
    def _run_simulation_with_data(self, symbol: str, df: pd.DataFrame):
        """단일 심볼로 시뮬레이션 (기존 방식)"""
        for idx, candle in df.iterrows():
            current_time = candle['datetime']
            
            # 포지션 있으면 청산 조건 체크
            if self.position:
                should_exit, exit_reason = self.check_exit_conditions(candle)
                
                if should_exit:
                    # 청산 가격 결정
                    if exit_reason == 'stop_loss':
                        exit_price = candle['low']  # Low에서 손절
                    elif exit_reason == 'trailing_stop':
                        exit_price = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
                    else:  # timeout
                        exit_price = candle['close']
                    
                    self.execute_exit(exit_price, current_time, exit_reason)
            
            # 포지션 없고 충분한 시간 남았으면 진입
            else:
                # 마지막 주기 시간 확보
                remaining_time = df['datetime'].iloc[-1] - current_time
                if remaining_time >= timedelta(hours=self.cycle_hours):
                    # 종가에 진입
                    self.execute_entry(symbol, candle['close'], current_time)
        
        # 시뮬레이션 종료 시 포지션 남아있으면 강제 청산
        if self.position:
            last_candle = df.iloc[-1]
            self.execute_exit(last_candle['close'], last_candle['datetime'], 'simulation_end')
        
        print(f"\n✅ 시뮬레이션 완료")
        print(f"  - 총 거래 횟수: {len(self.trades)}")
        print(f"  - 최종 잔고: {self.balance:.2f} USDT")
    
    def _run_simulation_with_scanner(self, start_date: str, end_date: str):
        """스캐너로 매 사이클마다 새 코인 선정"""
        current_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        print(f"📊 스캐너 시뮬레이션 시작...")
        print(f"  - 기간: {start_date} ~ {end_date}")
        
        cycle_count = 0
        
        while current_time < end_time:
            cycle_count += 1
            
            # 충분한 시간이 남지 않으면 종료
            remaining = (end_time - current_time).total_seconds() / 3600
            if remaining < self.cycle_hours:
                print(f"  - 남은 시간 부족 ({remaining:.1f}h < {self.cycle_hours}h). 종료.")
                break
            
            # 1. 스캐너로 코인 선정
            symbol = self.scan_random_coin()
            if not symbol:
                print(f"  Cycle {cycle_count}: 스캐너 실패, 스킵")
                current_time += timedelta(hours=self.cycle_hours)
                continue
            
            print(f"  Cycle {cycle_count}: {symbol} 선정")
            
            # 2. 해당 코인의 주기 데이터 조회
            cycle_end = current_time + timedelta(hours=self.cycle_hours)
            
            try:
                # 진입 시점의 현재가로 진입
                entry_candles = self.exchange.fetch_ohlcv(
                    symbol, '5m', 
                    since=int(current_time.timestamp() * 1000),
                    limit=1
                )
                
                if not entry_candles:
                    print(f"    - 진입 데이터 없음, 스킵")
                    current_time += timedelta(hours=self.cycle_hours)
                    continue
                
                entry_price = entry_candles[0][4]  # close
                
                # 진입
                self.execute_entry(symbol, entry_price, current_time)
                
                # 3. 주기 동안 5분마다 체크
                check_time = current_time
                
                while check_time < cycle_end:
                    check_time += timedelta(minutes=5)
                    
                    # 현재 캔들 조회
                    candles = self.exchange.fetch_ohlcv(
                        symbol, '5m',
                        since=int(check_time.timestamp() * 1000),
                        limit=1
                    )
                    
                    if not candles:
                        continue
                    
                    # 캔들을 Series로 변환
                    candle = pd.Series({
                        'timestamp': candles[0][0],
                        'open': candles[0][1],
                        'high': candles[0][2],
                        'low': candles[0][3],
                        'close': candles[0][4],
                        'volume': candles[0][5],
                        'datetime': check_time
                    })
                    
                    # 청산 조건 체크
                    should_exit, exit_reason = self.check_exit_conditions(candle)
                    
                    if should_exit:
                        if exit_reason == 'stop_loss':
                            exit_price = candle['low']
                        elif exit_reason == 'trailing_stop':
                            exit_price = self.position.peak_price * (1 - BacktestConfig.TS_CALLBACK_RATE / 100)
                        else:
                            exit_price = candle['close']
                        
                        self.execute_exit(exit_price, check_time, exit_reason)
                        print(f"    - 청산: {exit_reason} @ ${exit_price:.2f}")
                        break
                
                # 타임아웃이면 강제 청산
                if self.position:
                    exit_candles = self.exchange.fetch_ohlcv(
                        symbol, '5m',
                        since=int(cycle_end.timestamp() * 1000),
                        limit=1
                    )
                    exit_price = exit_candles[0][4] if exit_candles else entry_price
                    self.execute_exit(exit_price, cycle_end, 'timeout')
                    print(f"    - 청산: timeout @ ${exit_price:.2f}")
                
            except Exception as e:
                print(f"    - 에러: {e}")
            
            # 다음 사이클로
            current_time = cycle_end
        
        print(f"\n✅ 시뮬레이션 완료")
        print(f"  - 총 사이클: {cycle_count}")
        print(f"  - 총 거래 횟수: {len(self.trades)}")
        print(f"  - 최종 잔고: {self.balance:.2f} USDT")
        
    def generate_report(self) -> dict:
        """백테스트 리포트 생성"""
        if not self.trades:
            return {'error': '거래 내역 없음'}
        
        # 거래 통계
        winning_trades = [t for t in self.trades if t.pnl_percent > 0]
        losing_trades = [t for t in self.trades if t.pnl_percent <= 0]
        
        # 청산 사유별 통계
        exit_reasons = {}
        for trade in self.trades:
            reason = trade.exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        # 최대 잭팟 찾기
        max_jackpot = max(self.trades, key=lambda t: t.pnl_percent)
        
        # 생존 분석
        survival_days = None
        if self.trades:
            first_trade = self.trades[0]
            last_trade = self.trades[-1]
            survival_days = (last_trade.exit_time - first_trade.entry_time).days
        
        report = {
            'cycle_hours': self.cycle_hours,
            'initial_balance': BacktestConfig.INITIAL_BALANCE,
            'final_balance': round(self.balance, 2),
            'peak_balance': round(self.peak_balance, 2),
            'total_pnl': round(self.balance - BacktestConfig.INITIAL_BALANCE, 2),
            'total_pnl_percent': round((self.balance - BacktestConfig.INITIAL_BALANCE) / BacktestConfig.INITIAL_BALANCE * 100, 2),
            
            # 거래 통계
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(len(winning_trades) / len(self.trades) * 100, 2) if self.trades else 0,
            
            # 청산 사유
            'exit_reasons': exit_reasons,
            
            # 수익 통계
            'avg_pnl_percent': round(sum(t.pnl_percent for t in self.trades) / len(self.trades), 2),
            'avg_win_percent': round(sum(t.pnl_percent for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
            'avg_loss_percent': round(sum(t.pnl_percent for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
            
            # 최대 잭팟
            'max_jackpot': {
                'symbol': max_jackpot.symbol,
                'pnl_percent': round(max_jackpot.pnl_percent, 2),
                'exit_reason': max_jackpot.exit_reason,
                'entry_time': max_jackpot.entry_time.strftime('%Y-%m-%d %H:%M')
            },
            
            # 생존 분석
            'survival_days': survival_days,
            'bankruptcy_point': self.bankruptcy_point,
            
            # 상세 거래 내역
            'trades': [t.to_dict() for t in self.trades]
        }
        
        return report


def run_multi_cycle_backtest(symbol: str, start_date: str, end_date: str, use_scanner: bool = False) -> dict:
    """여러 주기로 백테스트 실행
    
    Args:
        symbol: 거래 심볼 (스캐너 모드에서는 무시됨)
        start_date: 시작일
        end_date: 종료일
        use_scanner: True이면 매 사이클마다 스캐너로 코인 선정
    """
    print(f"\n🎰 다중 주기 백테스트 시작")
    if use_scanner:
        print(f"  - Mode: 스캐너 (매 사이클 랜덤 선택)")
    else:
        print(f"  - Symbol: {symbol}")
    print(f"  - Period: {start_date} ~ {end_date}")
    print(f"  - Cycles: {BacktestConfig.TEST_CYCLES}")
    
    results = {}
    
    for cycle_hours in BacktestConfig.TEST_CYCLES:
        engine = BacktestEngine(cycle_hours, use_scanner=use_scanner)
        engine.run_simulation(symbol, start_date, end_date)
        results[f"{cycle_hours}h"] = engine.generate_report()
    
    # 최적 주기 분석
    best_cycle = max(results.items(), key=lambda x: x[1]['final_balance'])
    longest_survival = max(results.items(), key=lambda x: x[1]['survival_days'] or 0)
    
    summary = {
        'mode': 'scanner' if use_scanner else 'single_symbol',
        'symbol': 'RANDOM (Scanner)' if use_scanner else symbol,
        'period': f"{start_date} ~ {end_date}",
        'results': results,
        'recommendation': {
            'best_profit_cycle': best_cycle[0],
            'best_profit_balance': best_cycle[1]['final_balance'],
            'longest_survival_cycle': longest_survival[0],
            'longest_survival_days': longest_survival[1]['survival_days']
        }
    }
    
    return summary


def print_summary_report(summary: dict):
    """요약 리포트 출력"""
    print(f"\n{'='*80}")
    print(f"📊 백테스트 최종 리포트")
    print(f"{'='*80}")
    print(f"Symbol: {summary['symbol']}")
    print(f"Period: {summary['period']}")
    print(f"\n{'─'*80}")
    
    for cycle, result in summary['results'].items():
        print(f"\n🎯 주기: {cycle}")
        print(f"  초기 자산: {result['initial_balance']} USDT")
        print(f"  최종 잔고: {result['final_balance']} USDT (PNL: {result['total_pnl']:+.2f} USDT / {result['total_pnl_percent']:+.2f}%)")
        print(f"  최고 잔고: {result['peak_balance']} USDT")
        print(f"  거래 횟수: {result['total_trades']} (승: {result['winning_trades']}, 패: {result['losing_trades']})")
        print(f"  승률: {result['win_rate']}%")
        print(f"  평균 수익률: {result['avg_pnl_percent']}% (승: {result['avg_win_percent']}%, 패: {result['avg_loss_percent']}%)")
        print(f"  생존 일수: {result['survival_days']} 일")
        
        if result.get('bankruptcy_point'):
            bp = result['bankruptcy_point']
            print(f"  ⚠️ 파산 지점: {bp['trade_count']}번째 거래 (잔고: {bp['balance']:.2f} USDT)")
        
        print(f"  청산 사유: {result['exit_reasons']}")
        print(f"  🎉 최대 잭팟: {result['max_jackpot']['pnl_percent']}% ({result['max_jackpot']['symbol']}, {result['max_jackpot']['exit_reason']})")
    
    print(f"\n{'─'*80}")
    print(f"🏆 최종 추천")
    print(f"  - 최고 수익 주기: {summary['recommendation']['best_profit_cycle']} (잔고: {summary['recommendation']['best_profit_balance']} USDT)")
    print(f"  - 최장 생존 주기: {summary['recommendation']['longest_survival_cycle']} ({summary['recommendation']['longest_survival_days']} 일)")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    # 백테스트 예시
    symbol = 'BTC/USDT'  # 테스트용 (실제로는 스캐너에서 선정한 코인 사용)
    start_date = '2024-01-01'
    end_date = '2024-12-31'
    
    summary = run_multi_cycle_backtest(symbol, start_date, end_date)
    print_summary_report(summary)
    
    # JSON 저장
    output_file = f"backtest_result_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"💾 결과 저장: {output_file}")

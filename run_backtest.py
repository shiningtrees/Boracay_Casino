#!/usr/bin/env python3
"""
🎰 Boracay Casino Backtest Runner

사용법:
    python run_backtest.py BTC/USDT 2024-01-01 2024-12-31
    python run_backtest.py ETH/USDT 2024-06-01 2024-12-31 --cycles 48,72,96
"""

import sys
import argparse
from tests.backtester import run_multi_cycle_backtest, print_summary_report, BacktestConfig
import json
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description='Boracay Casino 백테스트 실행')
    parser.add_argument('symbol', nargs='?', default='SCANNER', help='거래 심볼 (예: BTC/USDT) 또는 SCANNER')
    parser.add_argument('start_date', help='시작일 (YYYY-MM-DD)')
    parser.add_argument('end_date', help='종료일 (YYYY-MM-DD)')
    parser.add_argument('--cycles', help='테스트할 주기 (시간, 쉼표 구분)', default='48,72,96')
    parser.add_argument('--output', '-o', help='출력 파일 경로', default=None)
    parser.add_argument('--scanner', action='store_true', help='스캐너 모드 (매 사이클 랜덤 선택)')
    
    args = parser.parse_args()
    
    # 스캐너 모드 판단
    use_scanner = args.scanner or args.symbol.upper() == 'SCANNER'
    
    # 주기 설정
    BacktestConfig.TEST_CYCLES = [int(c.strip()) for c in args.cycles.split(',')]
    
    print(f"\n🎰 Boracay Casino Backtest Engine")
    print(f"{'='*80}")
    if use_scanner:
        print(f"  Mode: 스캐너 (매 사이클마다 상위 20개 중 랜덤 선택)")
    else:
        print(f"  Symbol: {args.symbol}")
    print(f"  Period: {args.start_date} ~ {args.end_date}")
    print(f"  Cycles: {BacktestConfig.TEST_CYCLES}")
    print(f"{'='*80}\n")
    
    # 백테스트 실행
    try:
        summary = run_multi_cycle_backtest(
            args.symbol, 
            args.start_date, 
            args.end_date,
            use_scanner=use_scanner
        )
        print_summary_report(summary)
        
        # 결과 저장
        if args.output:
            output_file = args.output
        else:
            mode_str = 'scanner' if use_scanner else args.symbol.replace('/', '_')
            output_file = f"backtest_{mode_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"💾 결과 저장: {output_file}")
        
    except Exception as e:
        print(f"\n❌ 백테스트 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

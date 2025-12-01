"""
BacktestAdapter 테스트 스크립트
- 과거 데이터 로드 검증
- 백테스트 실행 검증
- 성능 메트릭 출력
"""
import sys
import os
import logging
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api_client.binance_client import BinanceClient
from backend.core.new_strategy.backtest_adapter import (
    BacktestAdapter,
    BacktestConfig,
)
from backend.core.new_strategy.orchestrator import (
    StrategyOrchestrator,
    OrchestratorConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


def main():
    print("=" * 80)
    print("BacktestAdapter 테스트")
    print("=" * 80)
    
    # 1. BinanceClient 초기화
    print("\n[1/4] BinanceClient 초기화")
    try:
        binance_client = BinanceClient()
        print("✅ BinanceClient 초기화 성공")
    except Exception as e:
        print(f"❌ BinanceClient 초기화 실패: {e}")
        return
    
    # 2. BacktestConfig 설정
    print("\n[2/4] BacktestConfig 설정")
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_date="2024-12-01",  # 최근 1개월
        end_date="2024-12-31",
        initial_balance=10000.0,
        leverage=10,
        commission_rate=0.0004,
        slippage_rate=0.0001,
    )
    print(f"   - Symbol: {config.symbol}")
    print(f"   - Period: {config.start_date} ~ {config.end_date}")
    print(f"   - Initial Balance: ${config.initial_balance}")
    print(f"   - Leverage: {config.leverage}x")
    print("✅ BacktestConfig 설정 완료")
    
    # 3. Orchestrator 초기화 (백테스트 모드)
    print("\n[3/4] Orchestrator 초기화")
    try:
        orch_config = OrchestratorConfig(
            symbol=config.symbol,
            leverage=config.leverage,
            enable_trading=False,  # 백테스트 모드 (실제 주문 없음)
        )
        orchestrator = StrategyOrchestrator(
            binance_client=binance_client,
            config=orch_config
        )
        print("✅ Orchestrator 초기화 성공")
    except Exception as e:
        print(f"❌ Orchestrator 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 백테스트 실행
    print("\n[4/4] 백테스트 실행")
    print("⚠️  주의: 백테스트는 데이터 양에 따라 수분~수십분 소요될 수 있습니다.")
    print("   (1분봉 1개월 = 약 43,000개 캔들)\n")
    
    try:
        adapter = BacktestAdapter(binance_client)
        
        results = adapter.run_backtest(
            orchestrator=orchestrator,
            config=config
        )
        
        print("\n" + "=" * 80)
        print("백테스트 결과")
        print("=" * 80)
        print(f"총 손익 (PNL):         {results['total_pnl']:>10.2f} USDT ({results['total_pnl_pct']:>6.2f}%)")
        print(f"총 거래 횟수:          {results['total_trades']:>10}")
        print(f"승률:                  {results['win_rate']:>10.2f}%")
        print(f"승리 거래:             {results['winning_trades']:>10}")
        print(f"패배 거래:             {results['losing_trades']:>10}")
        print(f"평균 승리:             {results['avg_win']:>10.2f} USDT")
        print(f"평균 손실:             {results['avg_loss']:>10.2f} USDT")
        print(f"Profit Factor:         {results['profit_factor']:>10.2f}")
        print(f"최대 낙폭 (MDD):       {results['max_drawdown']:>10.2f}%")
        print(f"Sharpe Ratio:          {results['sharpe_ratio']:>10.2f}")
        print("=" * 80)
        
        # 최근 거래 10개 출력
        if results['trades']:
            print("\n최근 거래 10개:")
            print("-" * 120)
            print(f"{'Entry Time':<20} {'Exit Time':<20} {'Dir':<6} {'Qty':<8} {'Entry':<10} {'Exit':<10} {'PNL':<12} {'Reason':<15}")
            print("-" * 120)
            for trade in results['trades'][-10:]:
                entry_time = trade['entry_time'].strftime("%Y-%m-%d %H:%M:%S") if isinstance(trade['entry_time'], datetime) else str(trade['entry_time'])
                exit_time = trade['exit_time'].strftime("%Y-%m-%d %H:%M:%S") if isinstance(trade['exit_time'], datetime) else str(trade['exit_time'])
                print(f"{entry_time:<20} {exit_time:<20} {trade['direction']:<6} {trade['quantity']:<8.4f} "
                      f"{trade['entry_price']:<10.2f} {trade['exit_price']:<10.2f} "
                      f"{trade['pnl']:>8.2f} USDT {trade['exit_reason']:<15}")
            print("-" * 120)
        
        print("\n✅ 백테스트 완료")
        
    except Exception as e:
        print(f"\n❌ 백테스트 실행 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨 (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()

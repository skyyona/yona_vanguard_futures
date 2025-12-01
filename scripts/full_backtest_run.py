"""
Full backtest runner (synthetic pilot).
Creates synthetic OHLCV data per symbol, runs a parameter grid sweep, and writes results to CSV.
Warning: This is a synthetic pilot harness. Replace data loader with real OHLCV source for production runs.
"""
import os
import csv
from backtesting_backend.core.strategy_simulator import StrategySimulator
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
import pandas as pd


def make_synthetic_df(n=1440, seed=2):
    idx = pd.date_range("2025-01-01", periods=n, freq="min")
    import random
    random.seed(seed)
    prices = [100 + i * 0.001 + (random.random() - 0.5) * 0.5 for i in range(n)]
    vols = [200 + (random.random() * 500) for _ in range(n)]
    opens = [p - 0.1 for p in prices]
    highs = [p + 0.1 for p in prices]
    lows = [p - 0.2 for p in prices]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols}, index=idx)


def main():
    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    SYMBOLS = [f"SYM{i+1}" for i in range(6)]
    spike_factors = [1.4, 1.6, 1.8, 2.0]
    avg_periods = [10, 20, 50]
    proximities = [0.001, 0.002, 0.005]

    out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "full_backtest_results.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "spike_factor", "avg_period", "proximity", "profit", "total_trades", "win_rate", "max_drawdown_pct"])

        for symbol in SYMBOLS:
            df = make_synthetic_df(n=1440, seed=hash(symbol) % 1000)
            for vf in spike_factors:
                for av in avg_periods:
                    for prox in proximities:
                        params = {
                            "fast_ema_period": 3,
                            "slow_ema_period": 5,
                            "enable_volume_momentum": True,
                            "volume_spike_factor": vf,
                            "volume_avg_period": av,
                            "enable_sr_detection": True,
                            "enable_sr_filter": True,
                            "sr_proximity_threshold": prox,
                            "stop_loss_pct": 0.01,
                            "take_profit_pct": 0.02,
                            "position_size": 0.02,
                        }
                        res = sim.run_simulation(symbol, "1m", df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
                        writer.writerow([symbol, vf, av, prox, res.get("profit", 0.0), res.get("total_trades", 0), res.get("win_rate", 0.0), res.get("max_drawdown_pct", 0.0)])

    print("Full synthetic backtest complete. Results written to:", out_path)


if __name__ == "__main__":
    main()

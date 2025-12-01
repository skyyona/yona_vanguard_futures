"""
Lightweight backtest skeleton to run small pilot sweeps. This is a template/harness
that enumerates a small parameter grid and runs `StrategySimulator` for a handful of symbols.
It is intended for local testing and quick pilots; heavy parameter sweeps should use a job queue.

Usage (example):
    python scripts/backtest_skeleton.py

This script does NOT run large experiments by default; edit `SYMBOLS` and `GRID` for your pilot.
"""
from backtesting_backend.core.strategy_simulator import StrategySimulator
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
import pandas as pd


def load_sample_df():
    # small synthetic example - replace with real OHLCV loader in production
    idx = pd.date_range("2025-01-01", periods=300, freq="min")
    import random
    random.seed(1)
    prices = [100 + i * 0.02 + (random.random() - 0.5) * 0.2 for i in range(len(idx))]
    vols = [100 + (random.random() * 200) for _ in range(len(idx))]
    opens = [p - 0.05 for p in prices]
    highs = [p + 0.05 for p in prices]
    lows = [p - 0.1 for p in prices]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols}, index=idx)


def main():
    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    SYMBOLS = ["PILOT1", "PILOT2"]
    GRID = {
        "volume_spike_factor": [1.4, 1.8],
        "volume_avg_period": [10, 20],
        "sr_proximity_threshold": [0.001, 0.002],
    }

    df = load_sample_df()

    results = []
    for symbol in SYMBOLS:
        for vf in GRID["volume_spike_factor"]:
            for av in GRID["volume_avg_period"]:
                for prox in GRID["sr_proximity_threshold"]:
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
                    results.append({"symbol": symbol, "vf": vf, "av": av, "prox": prox, "profit": res.get("profit", 0.0), "trades": res.get("total_trades", 0)})

    print("Pilot results:")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()

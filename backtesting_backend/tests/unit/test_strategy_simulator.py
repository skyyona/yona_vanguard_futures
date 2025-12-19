from backtesting_backend.core.strategy_simulator import StrategySimulator


def test_simulator_runs_and_returns_summary():
    sim = StrategySimulator()
    out = sim.run_once(strategy="alpha", symbol="BTCUSDT", start="2025-01-01", end="2025-01-02")
    assert "strategy" in out and "events_count" in out

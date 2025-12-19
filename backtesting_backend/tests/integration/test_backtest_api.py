import pytest


def test_backtest_api_imports():
    try:
        from backtesting_backend.app.api.backtest_router import run_backtest
    except Exception as e:
        pytest.skip(f"Missing API router or FastAPI: {e}")

    # cannot run the full FastAPI app in this unit test; ensure function exists
    assert callable(run_backtest)

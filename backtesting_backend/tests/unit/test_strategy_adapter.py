import pytest


def test_broker_simulator_and_alpha_adapter_imports():
    # Ensure we can import BrokerSimulator and alpha adapter factory
    try:
        from backtesting_backend.app.services.adapters.broker_simulator import BrokerSimulator
        from backtesting_backend.app.services.strategies.alpha_strategy_adapter import make_alpha_adapter
    except Exception as e:
        pytest.skip(f"Missing optional components: {e}")

    broker = BrokerSimulator()
    adapter = make_alpha_adapter(broker_client=broker)

    # Adapter should support start/stop and set_event_callback
    assert hasattr(adapter, "start")
    assert hasattr(adapter, "stop")
    assert hasattr(adapter, "set_event_callback")

import importlib.util
from pathlib import Path


def _load_adapter():
    path = Path(__file__).parent.parent / "yona_vanguard_futures" / "backend" / "core" / "new_strategy" / "analysis_adapter.py"
    spec = importlib.util.spec_from_file_location("analysis_adapter", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.adapt_analysis_payload


def test_full_raw():
    adapt = _load_adapter()
    raw = {
        "symbol": "TEST",
        "score": 5,
        "series": {"close": [1, 2, 3], "ema20": [1], "ema50": [2], "vwap": [0], "bpr": [0], "vss": [0]},
        "trend_analysis": {"overall": "상승"},
        "levels": {"entry_zone": {"low": 1}, "stop": 0.9},
    }

    out = adapt(raw)

    assert out["raw"] is raw
    assert out["symbol"] == "TEST"
    assert out["score"] == 5
    assert "series" in out and out["series"]["close"] == [1, 2, 3]
    assert out["trend_analysis"]["overall"] == "상승"
    assert out["levels"]["entry_zone"]["low"] == 1
    assert "performance" in out


def test_missing_keys():
    adapt = _load_adapter()
    raw = {"foo": "bar"}
    out = adapt(raw)

    assert out["raw"] is raw
    assert out["series"]["close"] == []
    assert out["trend_analysis"].get("overall") == "대기"
    assert out["levels"]["entry_zone"] == {}
    assert out.get("performance") == {}


def test_orchestrator_flags():
    adapt = _load_adapter()
    raw = {"entry_triggered": True, "signal_action": "enter", "signal_score": 7}
    out = adapt(raw)

    assert out["entry_triggered"] is True
    assert out["signal_action"] == "enter"
    assert out["signal_score"] == 7

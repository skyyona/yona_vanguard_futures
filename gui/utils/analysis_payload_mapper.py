import json
from typing import Any, Dict


def _parse_parameters(r: Dict[str, Any]) -> Dict[str, Any]:
    params = {}
    if isinstance(r.get("parameters_parsed"), dict):
        return r.get("parameters_parsed") or {}
    p = r.get("parameters")
    if isinstance(p, dict):
        return p
    if isinstance(p, str):
        try:
            return json.loads(p)
        except Exception:
            return {}
    return {}


def ensure_ui_payload(raw: Any) -> Dict[str, Any]:
    """Ensure the given raw analysis payload is in the UI-shaped form.

    If `raw` already contains a `data` key, return it unchanged.
    If `raw` looks like a flat DB row (has run_id/final_balance/etc),
    map it into the expected `{"data": {...}}` structure.
    """
    if not isinstance(raw, dict):
        return {"data": {}}

    # If already UI-shaped, no-op
    if "data" in raw and isinstance(raw.get("data"), dict):
        return raw

    # Heuristic: flat DB row
    if any(k in raw for k in ("run_id", "final_balance", "profit_percentage", "parameters")):
        params = _parse_parameters(raw) or {}

        try:
            profit = float(raw.get("profit_percentage") or raw.get("profit") or 0.0)
        except Exception:
            profit = 0.0
        try:
            max_dd = float(raw.get("max_drawdown") or raw.get("max_drawdown_pct") or 0.0)
        except Exception:
            max_dd = 0.0
        try:
            total_trades = int(raw.get("total_trades") or 0)
        except Exception:
            total_trades = 0
        try:
            win_rate = float(raw.get("win_rate") or 0.0)
        except Exception:
            win_rate = 0.0

        perf = {
            "profit_percentage": profit,
            "max_drawdown_pct": max_dd,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "aborted_early": bool(raw.get("aborted_early", False)),
            "insufficient_trades": bool(total_trades < 5),
        }

        mapped = {
            "symbol": raw.get("symbol"),
            "run_id": raw.get("run_id"),
            "initial_balance": float(raw.get("initial_balance") or 0.0),
            "final_balance": float(raw.get("final_balance") or 0.0),
            "created_at": raw.get("created_at"),
            "period": raw.get("period", "1w"),
            "interval": raw.get("interval", "1m"),
            "volatility": raw.get("volatility", 0.0) or 0.0,
            "best_parameters": params,
            "performance": perf,
            "leverage_recommendation": raw.get("leverage_recommendation") or {},
            "listing_meta": raw.get("listing_meta") or {"days_since_listing": 999, "is_new_listing": False, "new_listing_strategy_applied": False},
            "scenarios": raw.get("scenarios") or {},
            "strategy_performance": raw.get("strategy_performance") or [perf],
            "trade_logs": raw.get("trade_logs") or [],
            "engine_results": {
                "alpha": {"executable_parameters": params},
                "beta": {},
                "gamma": {},
            },
        }
        return {"data": mapped}

    # Fallback: return an empty data wrapper
    return {"data": raw.get("data") or {}}

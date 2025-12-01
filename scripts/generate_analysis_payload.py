"""Generate a JSON analysis payload for a symbol using local CSV + pilot results.

Usage:
  python scripts/generate_analysis_payload.py --symbol PIPPINUSDT --interval 5m

Outputs JSON to stdout.
"""
from __future__ import annotations
import argparse, json, os, sys
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    return p.parse_args()


def load_df(symbol: str, interval: str):
    fname = os.path.join('data', f"{symbol}_{interval}.csv")
    if not os.path.exists(fname):
        raise SystemExit('Data file not found: ' + fname)
    df = pd.read_csv(fname, parse_dates=[0], index_col=0)
    return df


def load_pilot_results(symbol: str):
    fname = os.path.join('results', f"{symbol.lower()}_pilot_results.csv")
    if not os.path.exists(fname):
        return None
    df = pd.read_csv(fname)
    return df


def compute_volatility(df: pd.DataFrame):
    # simple per-bar volatility in percent (std of pct_change * 100)
    s = df['close'].pct_change().dropna()
    if s.empty:
        return 0.0
    vol = float(s.std()) * 100.0
    return vol


def best_pilot_metrics(results_df: pd.DataFrame):
    if results_df is None or results_df.empty:
        return {}
    # prefer highest profit_pct
    if 'profit_pct' in results_df.columns:
        try:
            best = results_df.loc[results_df['profit_pct'].idxmax()]
        except Exception:
            best = results_df.iloc[0]
    else:
        best = results_df.iloc[0]
    out = {}
    for k in ['profit','profit_pct','total_trades','win_rate','max_drawdown_pct']:
        if k in best.index:
            out[k] = best[k]
    return out


def build_analysis(symbol: str, interval: str):
    df = load_df(symbol, interval)
    res_df = load_pilot_results(symbol)
    analyzer = StrategyAnalyzer()

    volatility = compute_volatility(df)
    metrics = best_pilot_metrics(res_df)

    engine_keys = ['alpha','beta','gamma']
    engine_results = {}
    confidences = {}
    for ek in engine_keys:
        h = analyzer.heuristics_for_new_listing(df, engine_key=ek, sim_min_candles=200)
        # ensure executable_parameters is serializable
        ep = h.get('executable_parameters', {}) or {}
        engine_results[ek] = {
            'executable_parameters': ep,
            'confidence': float(h.get('confidence') or 0.0),
            'notes': h.get('notes', [])
        }
        confidences[ek] = float(h.get('confidence') or 0.0)

    # best engine by confidence
    best_engine = max(confidences.items(), key=lambda x: x[1])[0].capitalize() if confidences else 'Alpha'

    # risk_management: synthesize from best engine params
    best_ep = engine_results.get(best_engine.lower(), {}).get('executable_parameters', {})
    risk_management = {}
    if 'stop_loss_pct' in best_ep:
        risk_management['stop_loss'] = best_ep.get('stop_loss_pct')
    if 'trailing_stop_pct' in best_ep:
        risk_management['trailing_stop'] = best_ep.get('trailing_stop_pct')
    # force_leverage if present
    if 'leverage' in best_ep:
        risk_management['force_leverage'] = best_ep.get('leverage')

    analysis = {
        'symbol': symbol,
        'best_engine': best_engine,
        'volatility': volatility,
        'metrics': metrics,
        'risk_management': risk_management,
        'executable_parameters': engine_results.get(best_engine.lower(), {}).get('executable_parameters', {}),
        'engine_results': engine_results,
        'is_new_listing': len(df) < 200,
        'data_missing': False if len(df) > 0 else True,
        'confidence': float(sum(confidences.values())/len(confidences)) if confidences else 0.0,
    }
    return analysis


def main():
    args = parse_args()
    out = build_analysis(args.symbol.upper(), args.interval)
    # sanitize numpy/pandas types to native python for JSON
    def _sanitize(v):
        import numpy as _np
        if isinstance(v, dict):
            return {k: _sanitize(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [_sanitize(x) for x in v]
        if isinstance(v, tuple):
            return tuple(_sanitize(list(v)))
        if isinstance(v, _np.generic):
            try:
                return v.item()
            except Exception:
                return int(v)
        try:
            # pandas NA/nan protection
            if v is pd.NA:
                return None
        except Exception:
            pass
        return v

    out_s = _sanitize(out)
    print(json.dumps(out_s, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()

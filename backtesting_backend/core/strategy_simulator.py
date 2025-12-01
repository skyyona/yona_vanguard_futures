from typing import Dict, Any, List
import pandas as pd
from dataclasses import dataclass
import math

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


@dataclass
class TradeRecord:
    entry_time: int
    entry_price: float
    exit_time: int | None = None
    exit_price: float | None = None
    pnl: float | None = None


class StrategySimulator:
    def __init__(self, analyzer: StrategyAnalyzer | None = None):
        self.analyzer = analyzer or StrategyAnalyzer()

    def run_simulation(self, symbol: str, interval: str, df: pd.DataFrame, initial_balance: float, leverage: int, strategy_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Run a simple backtest simulation over the DataFrame.

        This is a simplified simulator for PoC and will approximate PnL using close prices.
        """
        results: Dict[str, Any] = {}

        # compute indicators and signals
        # If the necessary indicator columns already exist on the dataframe (e.g. cached),
        # skip recalculation to save CPU. Detect by checking expected EMA columns and
        # optional volume momentum columns when enabled.
        fast = int(strategy_parameters.get("fast_ema_period", 9))
        slow = int(strategy_parameters.get("slow_ema_period", 21))
        ema_fast_col = f"ema_fast_{fast}"
        ema_slow_col = f"ema_slow_{slow}"

        need_calc = True
        try:
            if ema_fast_col in df.columns and ema_slow_col in df.columns:
                # if volume momentum is requested, ensure its columns are present
                if strategy_parameters.get("enable_volume_momentum"):
                    if "VolumeSpike" in df.columns and "VWAP" in df.columns:
                        need_calc = False
                else:
                    need_calc = False
        except Exception:
            need_calc = True

        if need_calc:
            df2 = self.analyzer.calculate_indicators(df, strategy_parameters)
        else:
            # use the provided df directly (assumed to already contain indicators)
            df2 = df.copy()

        # allow callers to supply precomputed signals and skip re-generation
        if not strategy_parameters.get("use_precomputed_signals", False):
            df2 = self.analyzer.generate_signals(df2, strategy_parameters)
        else:
            # assume df2 already contains `buy_signal`/`sell_signal`
            df2 = df2

        # Volume spike detection: compute rolling median volume and multiplier if requested
        try:
            if strategy_parameters.get("enable_volume_spike_filter"):
                lookback = int(strategy_parameters.get("vol_spike_lookback", 10))
                med_col = f"vol_med_{lookback}"
                mult_col = "vol_mult"
                if med_col not in df2.columns:
                    df2[med_col] = df2["volume"].rolling(window=lookback, min_periods=1).median()
                if mult_col not in df2.columns:
                    # avoid division by zero
                    df2[mult_col] = df2.apply(lambda r: (float(r["volume"]) / float(r[med_col])) if r.get(med_col) and float(r[med_col]) > 0 else 0.0, axis=1)
        except Exception:
            # non-fatal: continue without volume spike columns
            pass

        balance = initial_balance
        position = None
        trades: List[Dict[str, Any]] = []
        balance_history: List[float] = [balance]
        aborted_early = False

        # risk and execution parameters
        stop_loss_pct = float(strategy_parameters.get("stop_loss_pct", 0.005))  # 0.5% default
        take_profit_pct = float(strategy_parameters.get("take_profit_pct", 0.0))
        trailing_stop_pct = float(strategy_parameters.get("trailing_stop_pct", 0.0))
        fee_pct = float(strategy_parameters.get("fee_pct", 0.0))
        slippage_pct = float(strategy_parameters.get("slippage_pct", 0.0))

        # position sizing policy support
        # legacy: numeric 'position_size' interpreted as units; preferred: dict 'position_size_policy'
        position_size_raw = strategy_parameters.get("position_size", None)
        position_size_policy = strategy_parameters.get("position_size_policy", None)
        if position_size_policy is None and position_size_raw is not None:
            # support old callers by treating numeric as capital_fraction
            try:
                pct = float(position_size_raw)
                position_size_policy = {"method": "capital_fraction", "value": pct}
            except Exception:
                position_size_policy = {"method": "capital_fraction", "value": 1.0}

        no_compounding = bool(strategy_parameters.get("no_compounding", False))

        # early-stop and minimum trade safeguards
        early_stop_frac = float(strategy_parameters.get("early_stop_balance_frac", 0.0))
        min_trades_required = int(strategy_parameters.get("min_trades", 0))

        for idx, row in df2.iterrows():
            price = float(row["close"]) if "close" in row else float(row.close)

            if position is None and row.get("buy_signal"):
                # volume-spike filter: if enabled, skip entries when current volume is anomalously high
                try:
                    if strategy_parameters.get("enable_volume_spike_filter"):
                        thresh = float(strategy_parameters.get("vol_spike_threshold", 5.0))
                        vol_mult = float(row.get("vol_mult") or 0.0)
                        if vol_mult and vol_mult >= thresh:
                            # skip this entry (treat as no signal)
                            continue
                except Exception:
                    # if any error in filter evaluation, fall back to allowing entry
                    pass
                # Enter long at market price (apply slippage)
                entry_price = price
                entry_price_effective = entry_price * (1 + slippage_pct)
                # determine sizing (units) based on policy
                balance_for_sizing = initial_balance if no_compounding else balance
                units = None
                if position_size_policy and isinstance(position_size_policy, dict):
                    method = position_size_policy.get("method", "capital_fraction")
                    val = float(position_size_policy.get("value", 1.0))
                    if method == "capital_fraction":
                        # allocate val fraction of equity as position notional, then convert to units considering leverage
                        notional = balance_for_sizing * val
                        # with leverage, position notional = units * entry_price / leverage_effect? treat as leveraged exposure
                        # compute units so that exposure = notional * leverage -> units = (notional * leverage) / entry_price_effective
                        units = (notional * leverage) / entry_price_effective if entry_price_effective > 0 else 0.0
                    elif method == "risk_per_trade":
                        # val is fraction of capital to risk (e.g., 0.01 for 1%)
                        risk_amount = balance_for_sizing * val
                        # units such that if price moves by stop_loss_pct, loss equals risk_amount: units = risk_amount / (stop_loss_pct * entry_price_effective)
                        sl = stop_loss_pct if stop_loss_pct > 0 else 0.001
                        units = risk_amount / (sl * entry_price_effective) if (sl * entry_price_effective) > 0 else 0.0
                    else:
                        # fallback: treat as fraction
                        notional = balance_for_sizing * float(position_size_policy.get("value", 1.0))
                        units = (notional * leverage) / entry_price_effective if entry_price_effective > 0 else 0.0
                else:
                    # legacy numeric units or default full unit
                    try:
                        units = float(position_size_raw) if position_size_raw is not None else 1.0
                    except Exception:
                        units = 1.0

                entry_fee = entry_price_effective * units * fee_pct
                position = {
                    "entry_price": entry_price,
                    "entry_price_effective": entry_price_effective,
                    "entry_fee": entry_fee,
                    "entry_index": idx,
                    "highest_price": entry_price,
                    "tp_price": (entry_price * (1 + take_profit_pct)) if take_profit_pct > 0 else None,
                    "trailing_stop_pct": trailing_stop_pct,
                    "stop_loss_pct": stop_loss_pct,
                    "units": units,
                }

            elif position is not None:
                exit_price = None
                exit_reason = None

                # update highest price for trailing stop
                if price > position["highest_price"]:
                    position["highest_price"] = price

                # 1) Take profit check
                if position.get("tp_price") is not None and price >= position.get("tp_price"):
                    exit_price = price
                    exit_reason = "TP"
                # 2) Trailing stop check
                elif position.get("trailing_stop_pct", 0) > 0 and price <= position["highest_price"] * (1 - position.get("trailing_stop_pct")):
                    exit_price = price
                    exit_reason = "TRAIL"
                # 3) Stop loss check
                elif price <= position["entry_price"] * (1 - position.get("stop_loss_pct", stop_loss_pct)):
                    exit_price = price
                    exit_reason = "SL"
                # 4) Signal-based close
                elif row.get("sell_signal"):
                    exit_price = price
                    exit_reason = "SELL"

                if exit_price is not None:
                    # apply slippage and fees on exit
                    exit_price_effective = exit_price * (1 - slippage_pct)
                    units = position.get("units", 0.0)
                    exit_fee = exit_price_effective * units * fee_pct
                    gross_pnl = (exit_price_effective - position["entry_price_effective"]) * units * leverage
                    net_pnl = gross_pnl - (position.get("entry_fee", 0.0) + exit_fee)
                    balance += net_pnl
                    trades.append({
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "entry_price_effective": position.get("entry_price_effective"),
                        "exit_price_effective": exit_price_effective,
                        "entry_fee": position.get("entry_fee", 0.0),
                        "exit_fee": exit_fee,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "exit_reason": exit_reason,
                        "entry_index": position.get("entry_index"),
                        "exit_index": idx,
                    })
                    # do not append here; we'll append per-bar equity below for consistent equity curve
                    position = None

            # append current equity for this bar (include unrealized PnL if position open)
            try:
                if position is not None:
                    units = position.get('units', 0.0)
                    unreal = (price - position.get('entry_price_effective', position.get('entry_price', 0.0))) * units * leverage
                    equity = balance + unreal - position.get('entry_fee', 0.0)
                else:
                    equity = balance
                balance_history.append(equity)
                # early-stop: if configured and equity falls below threshold, abort to save time
                try:
                    if early_stop_frac and initial_balance and equity <= (initial_balance * early_stop_frac):
                        aborted_early = True
                        break
                except Exception:
                    pass
            except Exception:
                balance_history.append(balance)

        # close open position at last price
        if position is not None:
            last_price = float(df2.iloc[-1]["close"])
            exit_price = last_price
            exit_price_effective = exit_price * (1 - slippage_pct)
            units = position.get("units", 0.0)
            exit_fee = exit_price_effective * units * fee_pct
            gross_pnl = (exit_price_effective - position["entry_price_effective"]) * units * leverage
            net_pnl = gross_pnl - (position.get("entry_fee", 0.0) + exit_fee)
            balance += net_pnl
            trades.append({
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "entry_price_effective": position.get("entry_price_effective"),
                "exit_price_effective": exit_price_effective,
                "entry_fee": position.get("entry_fee", 0.0),
                "exit_fee": exit_fee,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "exit_reason": "LAST",
                "entry_index": position.get("entry_index"),
                "exit_index": df2.index[-1],
            })
            # append final balance to equity curve
            balance_history.append(balance)

        # mark insufficient trades if below threshold
        total_trades = len(trades)
        insufficient_trades = False
        if min_trades_required and total_trades < min_trades_required:
            insufficient_trades = True
        profit = balance - initial_balance
        profit_pct = (profit / initial_balance) * 100 if initial_balance else 0.0
        wins = [t for t in trades if t.get("net_pnl", 0) > 0]
        win_rate = (len(wins) / total_trades) * 100 if total_trades else 0.0

        # compute max drawdown from balance history
        try:
            peak = -math.inf
            max_dd = 0.0
            for b in balance_history:
                if b > peak:
                    peak = b
                dd = (peak - b) / peak if peak and peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd
            max_drawdown_pct = max_dd * 100
        except Exception:
            max_drawdown_pct = 0.0

        results = {
            "initial_balance": initial_balance,
            "final_balance": balance,
            "profit": profit,
            "profit_percentage": profit_pct,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "max_drawdown_pct": max_drawdown_pct,
            "trades": trades,
            "aborted_early": aborted_early,
            "insufficient_trades": insufficient_trades,
            "min_trades_required": min_trades_required,
        }

        return results

from typing import Dict, Any


class RiskManager:
    """Simple risk manager for backtests: provides stop/take checks."""

    def __init__(self, stop_loss_pct: float = 0.02, take_profit_pct: float = 0.05):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def check_stop_take(self, entry_price: float, current_price: float) -> Dict[str, Any]:
        # returns dict indicating whether stop or take triggered
        change = (current_price - entry_price) / entry_price
        if change <= -self.stop_loss_pct:
            return {"action": "STOP", "change": change}
        if change >= self.take_profit_pct:
            return {"action": "TAKE", "change": change}
        return {"action": "NONE", "change": change}

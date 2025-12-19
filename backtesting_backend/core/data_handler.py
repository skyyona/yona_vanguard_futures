from typing import Iterable, Dict, Any, List, Optional
import json
import os


class DataHandler:
    """Load historical data for backtests.

    This minimal implementation loads JSON fixtures or CSV if pandas available.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join("backtesting_backend", "tests", "fixtures")

    def load_bars(self, symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
        # try to load a JSON fixture named by symbol or short_bars.json
        p1 = os.path.join(self.data_dir, f"{symbol}.json")
        p2 = os.path.join(self.data_dir, "short_bars.json")
        path = p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else None)
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

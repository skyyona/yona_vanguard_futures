from typing import Dict, Any, Iterable, Callable, List, Tuple
import itertools
from multiprocessing.pool import ThreadPool


class GridSearch:
    """Simple grid search optimizer.

    Usage:
        gs = GridSearch(param_grid)
        best_params, best_score = gs.search(objective_fn, max_workers=4)

    The `objective_fn` should accept a single dict of params and return a numeric score (higher is better).
    """

    def __init__(self, param_grid: Dict[str, Iterable[Any]]):
        self.param_grid = param_grid
        # precompute combinations
        keys = list(param_grid.keys())
        values = [list(param_grid[k]) for k in keys]
        self._keys = keys
        self._combos = [dict(zip(keys, prod)) for prod in itertools.product(*values)]

    def search(self, objective_fn: Callable[[Dict[str, Any]], float], max_workers: int = 1, timeout: float | None = None) -> Tuple[Dict[str, Any], float, List[Tuple[Dict[str, Any], float]]]:
        results: List[Tuple[Dict[str, Any], float]] = []

        def _eval(p):
            try:
                score = float(objective_fn(p))
            except Exception:
                score = float("-inf")
            return (p, score)

        if max_workers and max_workers > 1:
            with ThreadPool(processes=max_workers) as pool:
                for p, s in pool.imap_unordered(_eval, self._combos):
                    results.append((p, s))
        else:
            for combo in self._combos:
                results.append(_eval(combo))

        # sort by score desc
        results.sort(key=lambda x: x[1], reverse=True)
        best = results[0] if results else ({}, float("-inf"))
        return best[0], best[1], results

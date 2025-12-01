from backtesting_backend.optimizers.grid_search import GridSearch


def dummy_objective(params):
    # simple objective: maximize (a - 2*b)
    a = params.get("a", 0)
    b = params.get("b", 0)
    return a - 2 * b


def test_grid_search_basic():
    grid = {"a": [1, 2, 3], "b": [0, 1]}
    gs = GridSearch(grid)
    best_params, best_score, all_results = gs.search(dummy_objective, max_workers=2)
    assert best_params["a"] == 3
    assert best_params["b"] == 0
    assert best_score == 3

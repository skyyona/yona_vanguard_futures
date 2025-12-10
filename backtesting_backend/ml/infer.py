from typing import Any, Dict
import os


def load_model(path: str) -> Any:
    """Load a model for inference. This is a minimal stub for backtests.

    In real deployment this would load a PyTorch/TF model.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    # stub: return path as handle
    return {"model_path": path}


def predict(handle: Any, features) -> Dict[str, Any]:
    """Return a dummy prediction dict for the given features."""
    # For safety keep it deterministic and simple
    return {"score": 0.5, "action": "HOLD"}

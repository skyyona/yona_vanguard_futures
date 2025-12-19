import json
import os
from typing import Dict, Any


def train_dummy_model(out_dir: str, strategy_name: str = "alpha") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    model_dir = os.path.join(out_dir, strategy_name)
    os.makedirs(model_dir, exist_ok=True)
    # create a tiny dummy checkpoint file
    ckpt_path = os.path.join(model_dir, "checkpoint.pth")
    with open(ckpt_path, "w", encoding="utf-8") as f:
        f.write("DUMMY CHECKPOINT")

    metadata = {
        "strategy": strategy_name,
        "created_by": "train_dummy_model",
        "input_schema": "../schema.json",
    }
    with open(os.path.join(model_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    return {"model_dir": model_dir, "checkpoint": ckpt_path}


if __name__ == "__main__":
    print(train_dummy_model("backtesting_backend/ml/models"))

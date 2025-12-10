from typing import Dict, Any, List


def extract_features(bar: Dict[str, Any]) -> List[float]:
    # Simple feature vector: [open, high, low, close, volume]
    return [bar.get("open", 0.0), bar.get("high", 0.0), bar.get("low", 0.0), bar.get("close", 0.0), bar.get("volume", 0.0)]

from __future__ import annotations
import json, sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from scripts.generate_analysis_payload import build_analysis
from scripts.output_config import legacy_dir

for sym in ('PIPPINUSDT','INUSDT'):
    out = build_analysis(sym, '5m')
    fname = f'{sym.lower()}_analysis.json'
    def sanitize(v):
        try:
            import numpy as _np
        except Exception:
            _np = None
        if isinstance(v, dict):
            return {k: sanitize(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [sanitize(x) for x in v]
        if _np is not None and isinstance(v, _np.generic):
            try:
                return v.item()
            except Exception:
                return int(v)
        try:
            # pandas NA
            import pandas as _pd
            if v is _pd.NA:
                return None
        except Exception:
            pass
        return v

    out_s = sanitize(out)
    out_path = os.path.join(legacy_dir(), fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path,'w',encoding='utf-8') as f:
        json.dump(out_s, f, ensure_ascii=False, indent=2)
    print('Wrote', out_path)

import os

ROOT = os.getcwd()
OUTPUT_ROOT = os.environ.get('OUTPUT_ROOT', os.path.join(ROOT, 'outputs'))

def ensure(dirpath: str) -> str:
    os.makedirs(dirpath, exist_ok=True)
    return dirpath

def backtest_mtf_dir() -> str:
    d = os.path.join(OUTPUT_ROOT, 'backtests_mtf')
    return ensure(d)

def backtest_dir() -> str:
    d = os.path.join(OUTPUT_ROOT, 'backtests')
    return ensure(d)

def parity_dir() -> str:
    d = os.path.join(OUTPUT_ROOT, 'parity')
    return ensure(d)

def legacy_dir() -> str:
    d = os.path.join(OUTPUT_ROOT, 'legacy')
    return ensure(d)

def outputs_root() -> str:
    return ensure(OUTPUT_ROOT)

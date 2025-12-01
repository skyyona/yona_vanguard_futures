import traceback
import sys

try:
    import backtesting_backend.app_main as m
    print("IMPORT_OK")
except Exception:
    traceback.print_exc()
    sys.exit(3)

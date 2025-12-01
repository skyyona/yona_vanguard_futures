import time
import requests
import statistics

BACKTEST_URL = "http://127.0.0.1:8001/api/v1/backtest/strategy-analysis"

def measure(symbol='SQDUSDT', period='1w', interval='1h', trials=3, timeout=60):
    times = []
    print(f"Measuring backtest: symbol={symbol}, period={period}, interval={interval}, trials={trials}")
    for i in range(trials):
        params = {"symbol": symbol, "period": period, "interval": interval}
        t0 = time.monotonic()
        try:
            resp = requests.get(BACKTEST_URL, params=params, timeout=timeout)
            elapsed = time.monotonic() - t0
            if resp.ok:
                # optional: validate presence of engine_results
                data = resp.json().get('data', {})
                has_exec = bool(data.get('engine_results'))
                print(f"  trial {i+1}: {elapsed:.3f}s, status={resp.status_code}, engine_results={has_exec}")
            else:
                print(f"  trial {i+1}: {elapsed:.3f}s, status={resp.status_code} (error)")
            times.append(elapsed)
        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"  trial {i+1}: failed after {elapsed:.3f}s -> {e}")
    if times:
        print("Summary:")
        print(f"  min: {min(times):.3f}s, max: {max(times):.3f}s, mean: {statistics.mean(times):.3f}s, median: {statistics.median(times):.3f}s")
    else:
        print("No successful trials recorded.")


def main():
    tests = [
        ("SQDUSDT", "1w", "1h"),
        ("SQDUSDT", "1w", "1m"),
        ("BTCUSDT", "1d", "1m"),
    ]

    for symbol, period, interval in tests:
        measure(symbol=symbol, period=period, interval=interval, trials=3)
        print()


if __name__ == '__main__':
    main()

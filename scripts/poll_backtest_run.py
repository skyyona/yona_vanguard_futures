import urllib.request, urllib.error, json, time, sys, sqlite3, argparse, os

API_BASE = "http://127.0.0.1:8001/api/v1/backtest"
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'backtest_app.log')
ORC_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'logs', 'strategy')
DB_PATH = r"C:\Users\User\new\yona_vanguard_futures\yona_backtest.db"

parser = argparse.ArgumentParser()
parser.add_argument('--run', '-r', required=True)
parser.add_argument('--timeout', '-t', type=int, default=120)
parser.add_argument('--interval', '-i', type=int, default=5)
args = parser.parse_args()
run_id = args.run
timeout = args.timeout
interval = args.interval

def get_status(run_id):
    url = f"{API_BASE}/backtest_status/{run_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}

def get_result(run_id):
    url = f"{API_BASE}/backtest_result/{run_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}


def tail_file(path, lines=200):
    if not os.path.exists(path):
        return f"(missing) {path}"
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 1024
            data = b''
            while size > 0 and lines > 0:
                step = min(block, size)
                f.seek(size-step)
                chunk = f.read(step)
                data = chunk + data
                size -= step
                lines -= chunk.count(b'\n')
            return data.decode(errors='replace')
    except Exception as e:
        return f"(err reading {path}) {e}"

print(json.dumps({"action":"poll_start","run_id":run_id, "timeout": timeout, "interval": interval}))
start = time.time()
status = None
while True:
    status = get_status(run_id)
    print(json.dumps({"timestamp": int(time.time()*1000), "status_resp": status}, ensure_ascii=False))
    if isinstance(status, dict) and (status.get('status') in ('completed','failed') or status.get('status')=='not_found'):
        break
    if 'error' in status:
        # transient error, continue until timeout
        pass
    if time.time() - start > timeout:
        print(json.dumps({"action":"timeout"}))
        break
    time.sleep(interval)

print('\n--- fetching API result ---')
res = get_result(run_id)
print(json.dumps({"result_api": res}, ensure_ascii=False))

print('\n--- tail backtest_app.log (last ~200 lines) ---')
print(tail_file(LOG_PATH, lines=400))

print('\n--- tail latest Orchestrator log (if any) ---')
if os.path.isdir(ORC_LOG_DIR):
    files = sorted([os.path.join(ORC_LOG_DIR,f) for f in os.listdir(ORC_LOG_DIR) if f.startswith('Orchestrator_')], reverse=True)
    if files:
        print(files[0])
        print(tail_file(files[0], lines=400))
    else:
        print('(no orchestrator logs)')
else:
    print('(orchestrator log dir missing)')

print('\n--- DB entry for run_id (if any) ---')
if os.path.exists(DB_PATH):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT run_id, strategy_name, symbol, interval, start_time, end_time, initial_balance, final_balance, profit_percentage, total_trades, win_rate, parameters, created_at FROM backtest_results WHERE run_id=?', (run_id,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            print(json.dumps(dict(zip(cols,row)), ensure_ascii=False))
        else:
            print('(no DB row)')
        conn.close()
    except Exception as e:
        print(f'(db error) {e}')
else:
    print(f'(db missing) {DB_PATH}')

print('\n--- done ---')

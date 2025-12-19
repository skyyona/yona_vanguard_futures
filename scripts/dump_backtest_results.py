import sqlite3
import json
import sys

DB_PATH = r"C:\Users\User\new\yona_backtest.db"

def main():
    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    cur = conn.cursor()
    try:
        rows = cur.execute(
            "select run_id, strategy_name, symbol, interval, start_time, end_time, created_at, parameters from backtest_results order by created_at desc limit 50"
        ).fetchall()
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        conn.close()
        sys.exit(1)
    for r in rows:
        out = {
            "run_id": r[0],
            "strategy": r[1],
            "symbol": r[2],
            "interval": r[3],
            "start": r[4],
            "end": r[5],
            "created_at": r[6],
            "parameters": r[7],
        }
        print(json.dumps(out, ensure_ascii=False))
    conn.close()

if __name__ == '__main__':
    main()

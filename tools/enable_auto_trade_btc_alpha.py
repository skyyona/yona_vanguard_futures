import json

from engine_backend.db.manager import get_conn


SYMBOL = "BTCUSDT"
ENGINE = "alpha"


def main() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, symbol, engine_name, parameters_json FROM strategies WHERE symbol = ? AND engine_name = ?",
        (SYMBOL, ENGINE),
    )
    row = cur.fetchone()
    if row is None:
        print(f"[enable_auto] no strategy row found for {SYMBOL} / {ENGINE}")
        conn.close()
        return 1

    params = {}
    try:
        params = json.loads(row["parameters_json"] or "{}")
    except Exception as e:
        print("[enable_auto] failed to decode parameters_json:", e)

    # Enable auto trading in parameters (DRY_RUN is still enforced by LIVE_TRADING_ENABLED=false)
    params["auto_trade_enabled"] = True

    new_json = json.dumps(params)
    cur.execute(
        "UPDATE strategies SET parameters_json = ? WHERE id = ?",
        (new_json, row["id"]),
    )
    conn.commit()
    conn.close()

    print(f"[enable_auto] updated {SYMBOL} / {ENGINE} -> auto_trade_enabled=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

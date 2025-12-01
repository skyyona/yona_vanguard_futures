from fastapi.testclient import TestClient
from backtesting_backend.app_main import create_app

app = create_app()
with TestClient(app) as client:
    r = client.get('/api/v1/backtest/strategy-analysis', params={'symbol':'TESTCOIN','period':'1d','interval':'1m'})
    print('status', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)

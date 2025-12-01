"""StrategyOrchestrator 연동 스모크 테스트 (Mock BinanceClient + DataFetcher 캐시 주입)"""
import random
from typing import List

from backend.core.new_strategy import (
    StrategyOrchestrator, OrchestratorConfig,
    BinanceDataFetcher,
)

# 간단한 Fake BinanceClient: get_klines만 제공
class FakeBinanceClient:
    def __init__(self):
        self.base_price = 50000.0
        self.t = 0

    def get_mark_price(self, symbol: str):
        return {"markPrice": str(self.base_price)}

    def _series(self, n: int, drift: float) -> List[list]:
        arr = []
        price = self.base_price
        for i in range(n):
            # 상승 후 약간의 잡음
            price = price * (1.0 + drift) + random.uniform(-5, 5)
            o = price - 10
            h = price + 20
            l = price - 20
            c = price
            v = 1000 + (i % 20) * 50
            arr.append([
                1700000000000 + i * 60000,  # openTime
                f"{o}",  # open
                f"{h}",  # high
                f"{l}",  # low
                f"{c}",  # close
                f"{v}",  # volume
                1700000000000 + (i + 1) * 60000,  # closeTime
                f"{v * c}",  # quoteVol
                1000 + i,  # trades
            ])
        self.base_price = price
        return arr

    def get_klines(self, symbol: str, interval: str, limit: int = 500, startTime=None, endTime=None):
        # interval별로 완만한 추세 설정: 1m 가장 강하게 상승
        drift = 0.0003 if interval == "1m" else (0.00015 if interval == "3m" else 0.00005)
        return self._series(limit, drift)

    # ExecutionAdapter가 사용하는 메서드들
    def _round_qty_by_filters(self, symbol, raw_qty, price_hint=None):
        return {"ok": True, "qty": float(f"{raw_qty:.3f}")}

    def set_margin_type(self, symbol, isolated=True):
        return {"symbol": symbol, "marginType": "ISOLATED"}

    def set_leverage(self, symbol, leverage: int):
        return {"symbol": symbol, "leverage": leverage}

    def create_market_order(self, symbol: str, side: str, quantity: float):
        return {
            "orderId": 111,
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "{:.2f}".format(self.base_price),
            "executedQty": f"{quantity:.3f}",
            "fills": [],
        }

    def close_position_market(self, symbol: str, side: str = None):
        return {
            "orderId": 222,
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "{:.2f}".format(self.base_price),
            "executedQty": "0.010",
        }


if __name__ == "__main__":
    print("Orchestrator 스모크 테스트 실행")
    client = FakeBinanceClient()
    orch = StrategyOrchestrator(client, config=OrchestratorConfig(symbol="BTCUSDT", order_quantity=0.001))

    # warmup 데이터 로드
    import asyncio
    asyncio.run(orch.fetcher.fetch_historical_candles("BTCUSDT", "1m", limit=200))
    asyncio.run(orch.fetcher.fetch_historical_candles("BTCUSDT", "3m", limit=200))
    asyncio.run(orch.fetcher.fetch_historical_candles("BTCUSDT", "15m", limit=200))

    for i in range(5):
        out = orch.step()
        print(f"step {i+1}", out)

    print("✓ 스모크 완료")

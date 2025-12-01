"""연속 실행 루프 테스트 (Mock BinanceClient, 10초간 실행)"""
import asyncio
import random
from typing import List

from backend.core.new_strategy import (
    StrategyOrchestrator,
    OrchestratorConfig,
)


class FakeBinanceClient:
    def __init__(self):
        self.base_price = 50000.0
        self.t = 0
        self.call_count = 0

    def get_mark_price(self, symbol: str):
        return {"markPrice": str(self.base_price)}

    def _series(self, n: int, drift: float) -> List[list]:
        arr = []
        price = self.base_price
        for i in range(n):
            price = price * (1.0 + drift) + random.uniform(-10, 10)
            o = price - 10
            h = price + 30
            l = price - 30
            c = price
            v = 1000 + (i % 20) * 100 + random.uniform(0, 500)  # 거래량 변동
            arr.append([
                1700000000000 + i * 60000,
                f"{o}", f"{h}", f"{l}", f"{c}", f"{v}",
                1700000000000 + (i + 1) * 60000,
                f"{v * c}", 1000 + i,
            ])
        self.base_price = price
        return arr

    def get_klines(self, symbol: str, interval: str, limit: int = 500, startTime=None, endTime=None):
        self.call_count += 1
        drift = 0.0005 if interval == "1m" else (0.0003 if interval == "3m" else 0.0001)
        return self._series(limit, drift)

    def _round_qty_by_filters(self, symbol, raw_qty, price_hint=None):
        return {"ok": True, "qty": float(f"{raw_qty:.3f}")}

    def set_margin_type(self, symbol, isolated=True):
        return {"symbol": symbol, "marginType": "ISOLATED"}

    def set_leverage(self, symbol, leverage: int):
        return {"symbol": symbol, "leverage": leverage}

    def create_market_order(self, symbol: str, side: str, quantity: float):
        return {
            "orderId": random.randint(10000, 99999),
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "{:.2f}".format(self.base_price),
            "executedQty": f"{quantity:.3f}",
            "fills": [],
        }

    def close_position_market(self, symbol: str, side: str = None):
        return {
            "orderId": random.randint(10000, 99999),
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "{:.2f}".format(self.base_price),
            "executedQty": "0.001",
        }


async def main():
    print("=" * 60)
    print("연속 실행 루프 테스트 (10초간)")
    print("=" * 60)
    
    client = FakeBinanceClient()
    
    # 이벤트 콜백 설정
    def on_event(result):
        for event in result.get("events", []):
            event_type = event.get("type")
            if event_type in ("ENTRY", "EXIT", "ENTRY_FAIL", "EXIT_FAIL"):
                print(f"[EVENT] {event_type}: {event}")
    
    config = OrchestratorConfig(
        symbol="BTCUSDT",
        order_quantity=0.001,
        enable_trading=True,
        loop_interval_sec=1.0,
    )
    
    orch = StrategyOrchestrator(client, config=config)
    orch.set_event_callback(on_event)
    
    print("\n✅ Orchestrator 초기화 완료")
    print(f"심볼: {config.symbol}, 루프 주기: {config.loop_interval_sec}초\n")
    
    # 비동기 루프 시작 (10초 후 자동 종료)
    print("🚀 연속 실행 시작...")
    
    # run_forever를 백그라운드 태스크로 실행
    task = asyncio.create_task(orch.run_forever())
    
    # 10초 대기
    await asyncio.sleep(10)
    
    # 종료
    print("\n⏹️  10초 경과, 종료 중...")
    orch.stop()
    
    # 태스크 완료 대기
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except asyncio.TimeoutError:
        print("⚠️  태스크 종료 타임아웃")
        task.cancel()
    
    # 최종 상태 출력
    status = orch.get_status()
    print("\n" + "=" * 60)
    print("최종 상태")
    print("=" * 60)
    print(f"실행 중: {status['running']}")
    print(f"포지션: {status['position']}")
    print(f"마지막 신호: {status.get('last_signal', {}).get('action', 'N/A')}")
    print(f"API 호출 횟수: {client.call_count}")
    
    print("\n✅ 테스트 완료")


if __name__ == "__main__":
    asyncio.run(main())

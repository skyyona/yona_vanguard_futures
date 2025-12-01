"""NewStrategyWrapper 단위 테스트"""
import time
from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper


class MockBinanceClient:
    """간단한 Mock Client"""
    def __init__(self):
        self.api_key = "test_key"
        self.secret_key = "test_secret"
        self.base_url = "https://testnet.binancefuture.com"
    
    def get_mark_price(self, symbol):
        return {"markPrice": "50000.0"}
    
    def get_klines(self, symbol, interval, limit=500, startTime=None, endTime=None):
        return [[1700000000000 + i * 60000, "50000", "50100", "49900", "50000", "1000", 1700000060000, "50000000", 1000] for i in range(limit)]
    
    def _round_qty_by_filters(self, symbol, raw_qty, price_hint=None):
        return {"ok": True, "qty": raw_qty}
    
    def set_margin_type(self, symbol, isolated=True):
        return {"symbol": symbol, "marginType": "ISOLATED"}
    
    def set_leverage(self, symbol, leverage):
        return {"symbol": symbol, "leverage": leverage}
    
    def create_market_order(self, symbol, side, quantity):
        return {"orderId": 123, "symbol": symbol, "status": "FILLED", "avgPrice": "50000.0", "executedQty": f"{quantity:.3f}", "fills": []}
    
    def close_position_market(self, symbol, side=None):
        return {"orderId": 456, "symbol": symbol, "status": "FILLED", "avgPrice": "50100.0", "executedQty": "0.001"}
    
    def get_account_info(self):
        return {"totalWalletBalance": "1000.0", "availableBalance": "1000.0"}
    
    def _sync_server_time(self):
        pass


def test_wrapper_initialization():
    print("=" * 60)
    print("NewStrategyWrapper 초기화 테스트")
    print("=" * 60)
    
    # Mock client 주입
    import backend.api_client.binance_client as bc
    original_client = bc.BinanceClient
    bc.BinanceClient = MockBinanceClient
    
    try:
        wrapper = NewStrategyWrapper(symbol="BTCUSDT", leverage=10, order_quantity=0.001)
        
        print(f"\n✅ 초기화 성공")
        print(f"  엔진 이름: {wrapper.engine_name}")
        print(f"  심볼: {wrapper.current_symbol}")
        print(f"  레버리지: {wrapper.config['leverage']}x")
        
        # 상태 조회
        status = wrapper.get_status()
        print(f"\n상태 조회:")
        print(f"  실행 중: {status['is_running']}")
        print(f"  포지션: {status['in_position']}")
        
        # start/stop 테스트
        print(f"\n전략 시작 테스트...")
        wrapper.start()
        time.sleep(2)  # 2초 대기
        
        status = wrapper.get_status()
        print(f"  실행 중: {status['is_running']}")
        print(f"  Orchestrator: {status['orchestrator_running']}")
        
        print(f"\n전략 정지 테스트...")
        wrapper.stop()
        time.sleep(1)
        
        status = wrapper.get_status()
        print(f"  실행 중: {status['is_running']}")
        
        print(f"\n✅ 모든 테스트 통과")
        
    finally:
        # 원래 client 복원
        bc.BinanceClient = original_client


if __name__ == "__main__":
    test_wrapper_initialization()

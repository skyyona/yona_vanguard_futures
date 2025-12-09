"""Beta 전략 - copied into backtesting_backend."""
from typing import Dict, Any, Optional
import threading
import time
import asyncio

from backtesting_backend.strategies.base_strategy import BaseStrategy
from backtesting_backend.new_strategy import (
    StrategyOrchestrator,
    OrchestratorConfig,
)


class BetaStrategy(BaseStrategy):
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, 
                 order_quantity: float = 0.001, 
                 binance_client: Optional[Any] = None):
        super().__init__("Beta", binance_client=binance_client)
        self.orch_config = OrchestratorConfig(
            symbol=symbol,
            leverage=leverage,
            order_quantity=order_quantity,
            enable_trading=True,
            loop_interval_sec=1.0,
        )
        self.orchestrator = StrategyOrchestrator(
            binance_client=self.binance_client,
            config=self.orch_config,
            auto_prepare_symbol=False,
        )
        self.orchestrator.set_event_callback(self._on_orchestrator_event)
        self.current_symbol = symbol
        self.config.update({
            "leverage": leverage,
            "capital_allocation": order_quantity * 50000,
        })
        print(f"[{self.engine_name}] Beta 전략 초기화 완료")

    def _on_orchestrator_event(self, result: Dict[str, Any]):
        for event in result.get("events", []):
            event_type = event.get("type")
            if self.gui_callback:
                try:
                    event_with_engine = {**event, "engine": self.engine_name}
                    self.gui_callback(event_with_engine)
                except Exception as e:
                    print(f"[{self.engine_name}] GUI 콜백 오류: {e}")
            if event_type == "ENTRY":
                self.in_position = True
                self.position_side = "LONG"
                self.entry_price = event.get("price", 0)
                self.position_quantity = event.get("quantity") or self.orch_config.order_quantity or 0.0
                self.total_trades += 1
                self._emit_message("INFO", f"진입: {self.entry_price:.2f}")
            elif event_type == "EXIT":
                if self.in_position and self.entry_price > 0:
                    exit_price = event.get("price", 0)
                    realized_pnl = self.close_position(exit_price)
                    self._emit_message("INFO", f"청산: {exit_price:.2f}, PNL: {realized_pnl:.2f} USDT")
                self.in_position = False
                self.position_side = None
                self.entry_price = 0.0
                self.position_quantity = 0.0
            elif event_type == "ENTRY_FAIL":
                self._emit_message("ERROR", f"진입 실패: {event.get('error')}")
            elif event_type == "WARMUP_FAIL":
                error = event.get("error", "Unknown error")
                print(f"[{self.engine_name}] ❌ Warmup 실패: {error}")
                self.is_running = False
                self.is_active = False
                self._emit_message("ERROR", f"초기화 실패: {error}")
            elif event_type == "EXIT_FAIL":
                self._emit_message("ERROR", f"청산 실패: {event.get('error')}")

    def start(self) -> bool:
        if self.is_running:
            print(f"[{self.engine_name}] 이미 실행 중입니다.")
            return False
        self.is_active = True
        self.is_running = True
        self.orchestrator.start()
        print(f"[{self.engine_name}] 전략 시작됨 (Orchestrator 백그라운드 실행)")
        return True

    def stop(self) -> bool:
        if not self.is_running:
            print(f"[{self.engine_name}] 이미 정지되어 있습니다.")
            return False
        self.is_active = False
        self.is_running = False
        self.orchestrator.stop()
        print(f"[{self.engine_name}] 전략 정지됨")
        return True

    def get_status(self) -> Dict[str, Any]:
        base_status = super().get_status()
        orch_status = self.orchestrator.get_status()
        last_signal = orch_status.get("last_signal") or {}
        base_status.update({
            "orchestrator_running": orch_status.get("running", False),
            "last_signal_action": last_signal.get("action", "N/A"),
            "last_signal_score": last_signal.get("score", 0),
        })
        return base_status

    def evaluate_conditions(self) -> Optional[str]:
        return None

    def _apply_risk_management(self, current_price: float):
        pass

    def update_config(self, new_config: Dict[str, Any]):
        super().update_config(new_config)
        print(f"[{self.engine_name}] ⚠️  설정 변경은 재시작 후 적용됩니다")

    def execute_trade(self, signal: str) -> bool:
        return True

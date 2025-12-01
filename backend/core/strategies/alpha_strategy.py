"""Alpha 전략 - 기본 NewModular 전략"""
from typing import Dict, Any, Optional
import threading
import time
import asyncio

from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.new_strategy import (
    StrategyOrchestrator,
    OrchestratorConfig,
)


class AlphaStrategy(BaseStrategy):
    """
    Alpha 전략 - 신규 모듈형 전략 Alpha 버전
    
    기존 NewModular를 Alpha로 전환
    """
    
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, 
                 order_quantity: float = 0.001, 
                 binance_client: Optional[Any] = None):
        """
        Alpha 전략 초기화
        
        Args:
            symbol: 거래 심볼
            leverage: 레버리지
            order_quantity: 주문 수량
            binance_client: BinanceClient 인스턴스 (선택적, EngineManager에서 주입)
        """
        # ✅ BaseStrategy에 binance_client 전달 (의존성 주입)
        super().__init__("Alpha", binance_client=binance_client)
        
        # Orchestrator 설정
        self.orch_config = OrchestratorConfig(
            symbol=symbol,
            leverage=leverage,
            order_quantity=order_quantity,
            enable_trading=True,
            loop_interval_sec=1.0,
        )
        
        # Orchestrator 초기화 (binance_client는 부모에서 상속)
        self.orchestrator = StrategyOrchestrator(
            binance_client=self.binance_client,
            config=self.orch_config,
            auto_prepare_symbol=False,  # 설정 적용 버튼에서 명시적 호출
        )
        
        # 이벤트 콜백 설정
        self.orchestrator.set_event_callback(self._on_orchestrator_event)
        
        # 설정 동기화
        self.current_symbol = symbol
        self.config.update({
            "leverage": leverage,
            "capital_allocation": order_quantity * 50000,  # 대략적인 USDT 환산
        })
        
        print(f"[{self.engine_name}] Alpha 전략 초기화 완료")
        print(f"  심볼: {symbol}, 레버리지: {leverage}x, 수량: {order_quantity}")
    
    def _on_orchestrator_event(self, result: Dict[str, Any]):
        """Orchestrator 이벤트를 BaseStrategy 상태에 반영 + GUI로 전달"""
        for event in result.get("events", []):
            event_type = event.get("type")
            
            # GUI 콜백으로 모든 이벤트 전달 (새 이벤트 타입 포함)
            if self.gui_callback:
                try:
                    # 엔진명 추가
                    event_with_engine = {**event, "engine": self.engine_name}
                    self.gui_callback(event_with_engine)
                except Exception as e:
                    print(f"[{self.engine_name}] GUI 콜백 오류: {e}")
            
            if event_type == "ENTRY":
                self.in_position = True
                self.position_side = "LONG"
                self.entry_price = event.get("price", 0)
                # 진입 수량 기록 (이벤트 quantity 없으면 설정값 사용)
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
                # Warmup 실패 시 상태 동기화
                error = event.get("error", "Unknown error")
                print(f"[{self.engine_name}] ❌ Warmup 실패: {error}")
                self.is_running = False
                self.is_active = False
                self._emit_message("ERROR", f"초기화 실패: {error}")
            
            elif event_type == "EXIT_FAIL":
                self._emit_message("ERROR", f"청산 실패: {event.get('error')}")
    
    def start(self) -> bool:
        """전략 시작 (Orchestrator 백그라운드 실행)"""
        if self.is_running:
            print(f"[{self.engine_name}] 이미 실행 중입니다.")
            return False
        
        self.is_active = True
        self.is_running = True
        
        # Orchestrator 백그라운드 시작
        self.orchestrator.start()
        
        print(f"[{self.engine_name}] 전략 시작됨 (Orchestrator 백그라운드 실행)")
        return True
    
    def stop(self) -> bool:
        """전략 정지"""
        if not self.is_running:
            print(f"[{self.engine_name}] 이미 정지되어 있습니다.")
            return False
        
        self.is_active = False
        self.is_running = False
        
        # Orchestrator 중지
        self.orchestrator.stop()
        
        print(f"[{self.engine_name}] 전략 정지됨")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 반환 (BaseStrategy + Orchestrator 상태 통합)"""
        base_status = super().get_status()
        
        # Orchestrator 상태 추가
        orch_status = self.orchestrator.get_status()
        
        last_signal = orch_status.get("last_signal") or {}
        
        base_status.update({
            "orchestrator_running": orch_status.get("running", False),
            "last_signal_action": last_signal.get("action", "N/A"),
            "last_signal_score": last_signal.get("score", 0),
        })
        
        return base_status
    
    def evaluate_conditions(self) -> Optional[str]:
        """
        조건 평가 (BaseStrategy 인터페이스 구현)
        
        Returns:
            "BUY", "SELL", "CLOSE" 또는 None
        
        Note:
            실제 로직은 Orchestrator가 처리하므로 여기서는 더미 구현
            GUI가 이 메서드를 호출하더라도 Orchestrator가 독립적으로 동작
        """
        # Orchestrator가 백그라운드에서 처리하므로 None 반환
        return None
    
    def _apply_risk_management(self, current_price: float):
        """
        리스크 관리 적용 (BaseStrategy 인터페이스 구현)
        
        Note:
            실제 리스크 관리는 RiskManager가 처리하므로 더미 구현
        """
        # RiskManager가 처리
        pass
    
    def update_config(self, new_config: Dict[str, Any]):
        """설정 업데이트 (제한적 지원)"""
        super().update_config(new_config)
        
        # Orchestrator는 런타임 중 설정 변경 미지원
        # 재시작 필요
        print(f"[{self.engine_name}] ⚠️  설정 변경은 재시작 후 적용됩니다")
    
    def execute_trade(self, signal: str) -> bool:
        """
        거래 실행 (BaseStrategy 추상 메서드 구현)
        
        Note:
            실제 거래는 Orchestrator가 처리하므로 더미 구현
        """
        # Orchestrator의 ExecutionAdapter가 처리
        return True

"""기본 전략 추상 클래스"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import threading
import time


class BaseStrategy(ABC):
    """
    모든 자동매매 엔진 전략의 기본 클래스
    
    각 엔진(Alpha, Beta, Gamma)은 이 클래스를 상속받아
    고유한 전략 로직을 구현합니다.
    """
    
    def __init__(self, engine_name: str, binance_client: Optional[Any] = None):
        """
        전략 초기화
        
        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
            binance_client: BinanceClient 인스턴스 (선택적, 의존성 주입용)
                - 제공 시: 해당 인스턴스 사용 (공유 클라이언트)
                - 미제공 시: 내부에서 새로 생성 (독립 클라이언트, 하위 호환성)
        """
        self.engine_name = engine_name
        self.is_active = False
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()
        
        # ✅ 의존성 주입 패턴 적용
        if binance_client is not None:
            # 주입받은 공유 클라이언트 사용
            self.binance_client = binance_client
            print(f"[{engine_name}] ✅ 공유 BinanceClient 사용 (ID: {id(binance_client)})")
        else:
            # 하위 호환성: 독립 클라이언트 생성
            from backend.api_client.binance_client import BinanceClient
            self.binance_client = BinanceClient()
            print(f"[{engine_name}] ⚠️  독립 BinanceClient 생성 (ID: {id(self.binance_client)})")
        
        # 전략 상태
        self.current_symbol = None
        self.in_position = False
        self.position_side = None  # "LONG" or "SHORT"
        self.entry_price = 0.0
        self.position_quantity = 0.0
        self.current_pnl = 0.0
        self.total_trades = 0
        
        # 자금 배분 및 손익 추적
        self.designated_funds = 0.0  # 배분된 자금 (USDT)
        self.realized_pnl = 0.0  # 실현 손익 (USDT)
        self.previous_position_pnl = 0.0  # 이전 포지션의 실현 손익
        
        self._message_callback = None
        self.gui_callback = None  # GUI 이벤트 콜백 (각 전략에서 설정)
        
        # 전략 설정 (각 엔진에서 오버라이드 가능)
        self.config = {
            "capital_allocation": 100.0,  # USDT
            "leverage": 3,
            "max_position_size": 1000.0,
            "stop_loss_percent": 0.02,  # 2%
            "take_profit_percent": 0.05,  # 5%
        }
        
        print(f"[{self.engine_name}] 전략 초기화 완료")
    
    def start(self) -> bool:
        """
        전략 시작
        
        Returns:
            성공 여부
        """
        with self._lock:
            if self.is_running:
                print(f"[{self.engine_name}] 이미 실행 중입니다.")
                return False
            
            self.is_active = True
            self.is_running = True
            
            # 전략 실행 스레드 시작
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            
            print(f"[{self.engine_name}] 전략 시작됨")
            return True
    
    def stop(self) -> bool:
        """
        전략 정지
        
        Returns:
            성공 여부
        """
        with self._lock:
            if not self.is_running:
                print(f"[{self.engine_name}] 이미 정지되어 있습니다.")
                return False
            
            self.is_active = False
            self.is_running = False
            
            print(f"[{self.engine_name}] 전략 정지됨")
            return True
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        전략 설정 업데이트
        
        Args:
            new_config: 새로운 설정 딕셔너리
        """
        with self._lock:
            self.config.update(new_config)
            print(f"[{self.engine_name}] 설정 업데이트: {self.config}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        현재 전략 상태 반환
        
        Returns:
            상태 딕셔너리
        """
        return {
            "engine": self.engine_name,
            "is_running": self.is_running,
            "symbol": self.current_symbol,
            "in_position": self.in_position,
            "position_side": self.position_side,
            "entry_price": self.entry_price,
            "pnl_percent": self._calculate_pnl_percent(),
            "total_trades": self.total_trades,
        }
    
    def set_message_callback(self, callback):
        self._message_callback = callback
    
    def _emit_message(self, category: str, message: str):
        if self._message_callback:
            try:
                self._message_callback(category, message)
            except Exception:
                pass
    
    def set_designated_funds(self, amount: float):
        """
        배분 자금 설정
        
        Args:
            amount: 배분 금액 (USDT)
        """
        self.designated_funds = amount
        print(f"[{self.engine_name}] 배분 자금 설정: {amount:.2f} USDT")
    
    def _calculate_pnl_percent(self) -> float:
        """
        수익률 계산 (%)
        
        배분 자금 기준으로 계산
        """
        if not self.designated_funds or self.designated_funds <= 0:
            return 0.0
        
        # 실현 손익 기준으로 계산
        pnl_percent = (self.realized_pnl / self.designated_funds) * 100.0
        return pnl_percent
    
    def calculate_position_pnl(self, current_price: float) -> float:
        """
        현재 포지션의 미실현 손익 계산
        
        Args:
            current_price: 현재 가격
            
        Returns:
            미실현 손익 (USDT)
        """
        if not self.in_position or self.entry_price == 0:
            return 0.0
        
        if self.position_side == "LONG":
            pnl = (current_price - self.entry_price) / self.entry_price * self.designated_funds * self.config.get("leverage", 1)
        else:  # SHORT
            pnl = (self.entry_price - current_price) / self.entry_price * self.designated_funds * self.config.get("leverage", 1)
        
        return pnl
    
    def close_position(self, exit_price: float) -> float:
        """
        포지션 청산 및 실현 손익 계산
        
        Args:
            exit_price: 청산 가격
            
        Returns:
            실현 손익 (USDT, 양수=수익, 음수=손실)
        """
        if not self.in_position or self.entry_price == 0:
            return 0.0
        
        # 실현 손익 계산
        realized_pnl = self.calculate_position_pnl(exit_price)
        
        # 실현 손익 누적
        self.realized_pnl += realized_pnl
        
        # 포지션 정보 초기화
        previous_symbol = self.current_symbol
        self.in_position = False
        self.position_side = None
        self.entry_price = 0.0
        self.position_quantity = 0.0
        self.current_pnl = 0.0
        
        print(f"[{self.engine_name}] 포지션 청산: {previous_symbol}, 실현 손익: {realized_pnl:.2f} USDT")
        
        return realized_pnl
    
    def get_realized_pnl(self) -> float:
        """
        누적 실현 손익 조회
        
        Returns:
            실현 손익 (USDT)
        """
        return self.realized_pnl

    def get_open_position(self) -> Optional[Dict[str, Any]]:
        """현재 열린 포지션 정보를 표준 구조로 반환.

        Returns:
            dict | None: 포지션 없으면 None, 있으면 {
                symbol, side, entry_price, quantity
            }
        """
        if not self.in_position or not self.current_symbol or self.entry_price == 0:
            return None
        return {
            "symbol": self.current_symbol,
            "side": self.position_side,
            "entry_price": self.entry_price,
            "quantity": self.position_quantity
        }
    
    def reset_realized_pnl(self):
        """실현 손익 초기화"""
        self.realized_pnl = 0.0
        print(f"[{self.engine_name}] 실현 손익 초기화")
    
    def _run_loop(self):
        """전략 실행 루프 (별도 스레드)"""
        print(f"[{self.engine_name}] 실행 루프 시작")
        
        while self.is_running:
            try:
                if self.is_active:
                    # 1. 시장 데이터 수신 및 분석
                    self._update_market_data()
                    
                    # 2. 조건 평가
                    signal = self.evaluate_conditions()
                    
                    # 3. 시그널 처리
                    if signal:
                        self._handle_signal(signal)
                    
                    # 4. 리스크 관리
                    self._apply_risk_management()
                
                time.sleep(1)  # 1초 간격
                
            except Exception as e:
                print(f"[{self.engine_name}] 실행 루프 오류: {e}")
                time.sleep(5)
        
        print(f"[{self.engine_name}] 실행 루프 종료")
    
    def _update_market_data(self):
        """시장 데이터 업데이트 (각 엔진에서 구현)"""
        pass
    
    def _handle_signal(self, signal: str):
        """
        거래 시그널 처리
        
        Args:
            signal: 거래 시그널 ("BUY_LONG", "SELL_SHORT", "CLOSE_LONG", "CLOSE_SHORT")
        """
        if signal in ["BUY_LONG", "SELL_SHORT"] and not self.in_position:
            self.execute_trade(signal)
        elif signal in ["CLOSE_LONG", "CLOSE_SHORT"] and self.in_position:
            self.execute_trade(signal)
    
    def _apply_risk_management(self):
        """리스크 관리 적용 (손절/익절)"""
        if not self.in_position:
            return
        
        # 손절/익절 로직 (각 엔진에서 세부 구현)
        pass
    
    @abstractmethod
    def evaluate_conditions(self) -> Optional[str]:
        """
        진입/청산 조건 평가
        
        각 전략에서 반드시 구현해야 합니다.
        
        Returns:
            거래 시그널 또는 None
            - "BUY_LONG": 롱 포지션 진입
            - "SELL_SHORT": 숏 포지션 진입
            - "CLOSE_LONG": 롱 포지션 청산
            - "CLOSE_SHORT": 숏 포지션 청산
            - None: 조건 미충족
        """
        pass
    
    @abstractmethod
    def execute_trade(self, signal: str) -> bool:
        """
        거래 실행
        
        각 전략에서 반드시 구현해야 합니다.
        
        Args:
            signal: 거래 시그널
            
        Returns:
            성공 여부
        """
        pass

"""
자금 배분 관리자 - 각 엔진의 배분 자금 추적 및 실현 손익 관리
"""
from typing import Dict, Optional
from backend.utils.logger import setup_logger

logger = setup_logger()


class FundsAllocationManager:
    """
    각 엔진(Alpha, Beta, Gamma)의 배분 자금과 실현 손익을 관리하는 클래스
    
    역할:
    - 각 엔진의 Designated Funds 추적
    - 실현 손익 추적
    - Account total balance 계산
    """
    
    def __init__(self):
        """자금 배분 관리자 초기화"""
        # 각 엔진의 배분 자금 (USDT)
        self.allocations: Dict[str, float] = {
            "Alpha": 0.0,
            "Beta": 0.0,
            "Gamma": 0.0
        }
        
        # 각 엔진의 실현 손익 (USDT)
        self.realized_pnl: Dict[str, float] = {
            "Alpha": 0.0,
            "Beta": 0.0,
            "Gamma": 0.0
        }
        
        logger.info("FundsAllocationManager 초기화 완료")
    
    def set_allocation(self, engine_name: str, amount: float) -> bool:
        """
        특정 엔진의 배분 자금 설정
        
        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
            amount: 배분 금액 (USDT)
            
        Returns:
            성공 여부
        """
        if engine_name not in self.allocations:
            logger.warning(f"알 수 없는 엔진 이름: {engine_name}")
            return False
        
        old_amount = self.allocations[engine_name]
        self.allocations[engine_name] = max(0.0, amount)
        
        logger.info(f"{engine_name} 엔진 배분 자금 설정: {old_amount:.2f} → {amount:.2f} USDT")
        return True
    
    def remove_allocation(self, engine_name: str) -> float:
        """
        특정 엔진의 배분 자금 제거
        
        Args:
            engine_name: 엔진 이름
            
        Returns:
            제거된 배분 금액
        """
        if engine_name not in self.allocations:
            return 0.0
        
        amount = self.allocations[engine_name]
        self.allocations[engine_name] = 0.0
        
        logger.info(f"{engine_name} 엔진 배분 자금 제거: {amount:.2f} USDT")
        return amount
    
    def get_allocation(self, engine_name: str) -> float:
        """
        특정 엔진의 배분 자금 조회
        
        Args:
            engine_name: 엔진 이름
            
        Returns:
            배분 금액 (USDT)
        """
        return self.allocations.get(engine_name, 0.0)
    
    def get_total_allocated(self) -> float:
        """
        전체 배분 합계 조회
        
        Returns:
            전체 배분 금액 합계 (USDT)
        """
        return sum(self.allocations.values())
    
    def add_realized_pnl(self, engine_name: str, amount: float) -> None:
        """
        특정 엔진의 실현 손익 추가
        
        Args:
            engine_name: 엔진 이름
            amount: 실현 손익 (USDT, 양수=수익, 음수=손실)
        """
        if engine_name not in self.realized_pnl:
            logger.warning(f"알 수 없는 엔진 이름: {engine_name}")
            return
        
        self.realized_pnl[engine_name] += amount
        
        if amount >= 0:
            logger.info(f"{engine_name} 엔진 실현 수익 추가: +{amount:.2f} USDT (누적: {self.realized_pnl[engine_name]:.2f} USDT)")
        else:
            logger.info(f"{engine_name} 엔진 실현 손실 추가: {amount:.2f} USDT (누적: {self.realized_pnl[engine_name]:.2f} USDT)")
    
    def get_realized_pnl(self, engine_name: Optional[str] = None) -> float:
        """
        실현 손익 조회
        
        Args:
            engine_name: 엔진 이름 (None이면 전체 합계)
            
        Returns:
            실현 손익 (USDT)
        """
        if engine_name:
            return self.realized_pnl.get(engine_name, 0.0)
        else:
            return sum(self.realized_pnl.values())
    
    def calculate_account_total_balance(self, initial_investment: float) -> float:
        """
        Account total balance 계산
        
        공식:
        Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
        
        Args:
            initial_investment: 초기 투자금 (USDT)
            
        Returns:
            Account total balance (USDT)
        """
        total_allocated = self.get_total_allocated()
        total_realized_pnl = self.get_realized_pnl()
        
        account_total_balance = initial_investment - total_allocated + total_realized_pnl
        
        logger.debug(
            f"Account total balance 계산: "
            f"{initial_investment:.2f} - {total_allocated:.2f} + {total_realized_pnl:.2f} = {account_total_balance:.2f} USDT"
        )
        
        return account_total_balance
    
    def calculate_pnl_percent(self, initial_investment: float) -> float:
        """
        P&L % 계산
        
        공식:
        P&L % = (실현 손익 합계 / Initial Investment) * 100
        
        Args:
            initial_investment: 초기 투자금 (USDT)
            
        Returns:
            P&L % (퍼센트)
        """
        if initial_investment <= 0:
            return 0.0
        
        total_realized_pnl = self.get_realized_pnl()
        pnl_percent = (total_realized_pnl / initial_investment) * 100.0
        
        logger.debug(
            f"P&L % 계산: ({total_realized_pnl:.2f} / {initial_investment:.2f}) * 100 = {pnl_percent:.2f}%"
        )
        
        return pnl_percent
    
    def get_all_allocations(self) -> Dict[str, float]:
        """
        모든 엔진의 배분 자금 조회
        
        Returns:
            엔진별 배분 자금 딕셔너리
        """
        return self.allocations.copy()
    
    def get_all_realized_pnl(self) -> Dict[str, float]:
        """
        모든 엔진의 실현 손익 조회
        
        Returns:
            엔진별 실현 손익 딕셔너리
        """
        return self.realized_pnl.copy()
    
    def reset(self) -> None:
        """모든 배분 자금 및 실현 손익 초기화"""
        self.allocations = {
            "Alpha": 0.0,
            "Beta": 0.0,
            "Gamma": 0.0
        }
        self.realized_pnl = {
            "Alpha": 0.0,
            "Beta": 0.0,
            "Gamma": 0.0
        }
        logger.info("FundsAllocationManager 초기화 완료")



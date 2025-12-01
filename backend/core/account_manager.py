from typing import Dict, Any, Optional
from backend.utils.logger import setup_logger
from backend.api_client.binance_client import BinanceClient
from backend.core.funds_allocation_manager import FundsAllocationManager

logger = setup_logger()

class AccountManager:
    """계좌 정보 관리 클래스"""
    
    def __init__(self, binance_client: Optional[BinanceClient] = None, 
                 funds_allocation_manager: Optional[FundsAllocationManager] = None):
        self.binance_client = binance_client or BinanceClient()
        self.funds_allocation_manager = funds_allocation_manager or FundsAllocationManager()
        
        # 계좌 정보
        self.initial_capital: float = 0.0  # 투입 자금 (초기 자본)
        self.total_wallet_balance: float = 0.0  # 총 지갑 잔액 (USDT) - 바이낸스 API 값
        self.total_unrealized_pnl: float = 0.0  # 총 미실현 손익 (USDT)
        self.current_balance_usdt: float = 0.0  # 현재 USDT 잔액
        
        # 초기 자본 설정 여부
        self._initial_capital_set: bool = False
        
        logger.info("AccountManager 초기화 완료.")
    
    def set_initial_capital(self, capital: float, save_to_db: bool = False, db_path: Optional[str] = None, force: bool = False):
        """
        투입 자금(초기 자본)을 설정합니다.
        
        Args:
            capital: 초기 자본 금액
            save_to_db: DB에 저장할지 여부
            db_path: 데이터베이스 파일 경로 (save_to_db=True일 때 필요)
        """
        if capital > 0 or force:
            self.initial_capital = capital
            self._initial_capital_set = True
            logger.info(f"초기 자본 설정: {capital:,.2f} USDT")
            
            # DB 저장 (선택적)
            if save_to_db and db_path:
                import asyncio
                import aiosqlite
                from datetime import datetime
                
                async def save():
                    try:
                        now_utc = datetime.utcnow().isoformat()
                        async with aiosqlite.connect(db_path) as db:
                            await db.execute("""
                                INSERT OR REPLACE INTO app_settings (key, value, value_type, updated_at_utc, created_at_utc)
                                SELECT 'initial_capital', ?, 'float', ?, 
                                       COALESCE((SELECT created_at_utc FROM app_settings WHERE key = 'initial_capital'), ?)
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM app_settings WHERE key = 'initial_capital'
                                )
                                UNION ALL
                                SELECT 'initial_capital', ?, 'float', ?, created_at_utc
                                FROM app_settings
                                WHERE key = 'initial_capital'
                            """, (str(capital), now_utc, now_utc, str(capital), now_utc))
                            await db.commit()
                            logger.info(f"초기 자본 DB 저장 완료: {capital:,.2f} USDT")
                    except Exception as e:
                        logger.warning(f"초기 자본 DB 저장 실패: {e}")
                
                # 비동기 저장 실행
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(save())
                    else:
                        loop.run_until_complete(save())
                except RuntimeError:
                    # 이벤트 루프가 없으면 새로 생성
                    asyncio.run(save())
        else:
            logger.warning(f"유효하지 않은 초기 자본 값: {capital}")
    
    def update_account_info(self) -> bool:
        """바이낸스 API에서 최신 계좌 정보를 조회하여 업데이트합니다."""
        try:
            account_info = self.binance_client.get_account_info()
            
            if "error" in account_info:
                logger.warning(f"계좌 정보 조회 실패: {account_info.get('error')}")
                return False
            
            # 바이낸스 API 응답 구조:
            # totalWalletBalance: 총 지갑 잔액 (미실현 손익 포함된 현재 자산 가치)
            # totalUnrealizedProfit: 총 미실현 손익
            # totalMarginBalance: 총 마진 잔액
            # availableBalance: 사용 가능한 잔액
            
            # 총 지갑 잔액 (미실현 손익이 이미 반영된 현재 총 자산)
            self.total_wallet_balance = float(account_info.get("totalWalletBalance", 0.0))
            
            # 총 미실현 손익
            self.total_unrealized_pnl = float(account_info.get("totalUnrealizedProfit", 0.0))
            
            # USDT 잔액 찾기
            assets = account_info.get("assets", [])
            for asset in assets:
                if asset.get("asset") == "USDT":
                    self.current_balance_usdt = float(asset.get("walletBalance", 0.0))
                    break
            
            # 초기 자본이 설정되지 않았고, 현재 지갑 잔액이 있으면 초기 자본으로 설정
            # 첫 계좌 조회 시의 총 지갑 잔액을 초기 자본으로 설정
            # (totalWalletBalance는 이미 미실현 손익이 반영된 값이므로, 그 값을 초기 자본으로 사용)
            if not self._initial_capital_set and self.total_wallet_balance > 0:
                self.initial_capital = self.total_wallet_balance
                self._initial_capital_set = True
                logger.info(f"초기 자본 자동 설정: {self.initial_capital:,.2f} USDT")
                
                # DB 저장 (YonaService에서 처리하도록)
                # 여기서는 저장하지 않음 (YonaService에서 _save_app_setting 호출 필요)
            
            return True
            
        except Exception as e:
            logger.error(f"계좌 정보 업데이트 중 오류 발생: {e}", exc_info=True)
            return False
    
    def get_header_data(self) -> Dict[str, Any]:
        """
        헤더에 표시할 데이터를 반환합니다.
        
        계산 공식:
        - Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
        - P&L % = (실현 손익 합계 / Initial Investment) * 100
        """
        # Account total balance 계산 (배분 차감 + 실현 손익 반영)
        account_total_balance = self.funds_allocation_manager.calculate_account_total_balance(
            self.initial_capital
        )
        
        # P&L % 계산 (실현 손익만 반영)
        pnl_percent = self.funds_allocation_manager.calculate_pnl_percent(
            self.initial_capital
        )
        
        return {
            "initial_capital": self.initial_capital,
            "total_balance": account_total_balance,  # 배분 차감 후 잔액 + 실현 손익
            "pnl_percent": pnl_percent  # 실현 손익 기준 P&L %
        }
    
    def get_total_balance(self) -> float:
        """현재 총 지갑 잔액을 반환합니다."""
        return self.total_wallet_balance
    
    def get_unrealized_pnl(self) -> float:
        """현재 총 미실현 손익을 반환합니다."""
        return self.total_unrealized_pnl


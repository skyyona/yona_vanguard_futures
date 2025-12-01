"""주문 실행 어댑터 - BinanceClient 래핑 및 재시도/필터 검증"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time
import logging

from .data_structures import OrderResult, OrderFill, APIError

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRetryPolicy:
    max_attempts: int = 3
    base_backoff_sec: float = 0.5  # 지수 백오프 시작
    backoff_multiplier: float = 2.0


class ExecutionAdapter:
    """
    BinanceClient를 감싸서 다음을 제공:
    - 거래 필터 사전 검증 및 수량 정규화
    - 레버리지/마진 타입 설정
    - 주문 실행 재시도(지수 백오프)
    - 표준화된 OrderResult 반환
    """

    def __init__(self, binance_client, retry: Optional[ExecutionRetryPolicy] = None):
        self.client = binance_client
        self.retry = retry or ExecutionRetryPolicy()

    # ----------------------
    # 유틸/검증
    # ----------------------
    def normalize_quantity(self, symbol: str, raw_qty: float, price_hint: Optional[float] = None) -> Dict[str, Any]:
        try:
            if price_hint is None:
                mp = self.client.get_mark_price(symbol)
                price_hint = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else 0.0
            norm = self.client._round_qty_by_filters(symbol, raw_qty, price_hint=price_hint)
            return norm
        except Exception as e:
            return {"ok": False, "reason": f"normalize_error: {e}"}

    def prepare_symbol(self, symbol: str, leverage: int, isolated: bool = True) -> bool:
        # 마진 타입 설정
        mt = self.client.set_margin_type(symbol, isolated=isolated)
        if "error" in mt and not mt.get("alreadySet"):
            logger.error(f"마진 타입 설정 실패: {mt}")
            return False
        # 레버리지 설정
        lv = self.client.set_leverage(symbol, leverage)
        if "error" in lv:
            logger.error(f"레버리지 설정 실패: {lv}")
            return False
        return True

    # ----------------------
    # 주문 실행
    # ----------------------
    def place_market_long(self, symbol: str, quantity: float) -> OrderResult:
        # 1) 수량 정규화 사전 수행 (create_market_order에서도 실행되지만, 실패 사전 탐지 목적)
        norm = self.normalize_quantity(symbol, quantity)
        if not norm.get("ok"):
            return OrderResult(
                ok=False,
                symbol=symbol,
                error_message=norm.get("reason", "quantity normalization failed")
            )
        norm_qty = norm.get("qty", quantity)

        # 2) 재시도 정책으로 주문 실행
        attempt = 0
        delay = self.retry.base_backoff_sec
        last_err: Optional[str] = None
        while attempt < self.retry.max_attempts:
            attempt += 1
            try:
                resp = self.client.create_market_order(symbol, side="BUY", quantity=norm_qty)
                if "error" not in resp:
                    # 필터 메타 정보 포함
                    filter_meta = {
                        "rawQty": quantity,
                        "finalQty": norm_qty,
                        "stepSize": norm.get("stepSize"),
                        "minQty": norm.get("minQty"),
                        "minNotional": norm.get("minNotional"),
                        "notional": norm.get("notional"),
                        "nearMinNotional": norm.get("nearMinNotional")
                    }
                    return self._to_order_result_ok(symbol, resp, expected_side="BUY", filter_meta=filter_meta)
                else:
                    last_err = str(resp.get("error"))
                    logger.warning(f"시장가 주문 실패(시도 {attempt}/{self.retry.max_attempts}): {last_err}")
            except Exception as e:
                last_err = str(e)
                logger.error(f"주문 호출 예외(시도 {attempt}): {e}")

            if attempt < self.retry.max_attempts:
                time.sleep(delay)
                delay *= self.retry.backoff_multiplier

        return OrderResult(
            ok=False,
            symbol=symbol,
            error_message=last_err or "order_failed",
        )

    def close_market_long(self, symbol: str) -> OrderResult:
        attempt = 0
        delay = self.retry.base_backoff_sec
        last_err: Optional[str] = None
        while attempt < self.retry.max_attempts:
            attempt += 1
            try:
                resp = self.client.close_position_market(symbol, side="SELL")
                if "error" not in resp:
                    return self._to_order_result_ok(symbol, resp, expected_side="SELL")
                else:
                    last_err = str(resp.get("error"))
                    logger.warning(f"청산 실패(시도 {attempt}/{self.retry.max_attempts}): {last_err}")
            except Exception as e:
                last_err = str(e)
                logger.error(f"청산 호출 예외(시도 {attempt}): {e}")

            if attempt < self.retry.max_attempts:
                time.sleep(delay)
                delay *= self.retry.backoff_multiplier

        return OrderResult(
            ok=False,
            symbol=symbol,
            error_message=last_err or "close_failed",
        )

    # ----------------------
    # 매핑
    # ----------------------
    def _to_order_result_ok(self, symbol: str, resp: Dict[str, Any], expected_side: str, filter_meta: Optional[Dict[str, Any]] = None) -> OrderResult:
        try:
            fills_data = resp.get("fills") or []
            fills = [
                OrderFill(
                    price=float(f.get("price", 0)),
                    quantity=float(f.get("qty", f.get("quantity", 0))),
                    commission=float(f.get("commission", 0)),
                    commission_asset=str(f.get("commissionAsset", "USDT")),
                ) for f in fills_data
            ] if isinstance(fills_data, list) else None

            avg_price = float(resp.get("avgPrice", 0)) if resp.get("avgPrice") is not None else None
            executed_qty = float(resp.get("executedQty", 0)) if resp.get("executedQty") is not None else None

            return OrderResult(
                ok=True,
                symbol=symbol,
                order_id=int(resp.get("orderId")) if resp.get("orderId") is not None else None,
                side=expected_side,
                avg_price=avg_price,
                executed_qty=executed_qty,
                fills=fills,
                timestamp=int(time.time() * 1000),
                filter_meta=filter_meta,
            )
        except Exception as e:
            logger.error(f"OrderResult 매핑 오류: {e}")
            return OrderResult(
                ok=True,  # 응답 자체는 성공이었으므로 ok 유지
                symbol=symbol,
                side=expected_side,
                timestamp=int(time.time() * 1000),
                error_message=f"mapping_error: {e}",
            )

import requests
import hmac
import hashlib
import time
import threading
import urllib.parse
from typing import Optional, Dict, Any
from backend.utils.config_loader import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_BASE_URL
from backend.utils.logger import setup_logger
from backend.api.rate_limit_manager import rate_limit_manager

logger = setup_logger()

class BinanceClient:
    """바이낸스 선물 API 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or BINANCE_API_KEY
        self.secret_key = secret_key or BINANCE_SECRET_KEY
        self.base_url = (base_url or BINANCE_BASE_URL).rstrip('/')
        
        if not self.api_key or not self.secret_key:
            logger.warning("Binance API 키 또는 시크릿 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            # 에러를 발생시키지 않고 경고만 출력 (테스트 환경 등)
        
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                'X-MBX-APIKEY': self.api_key
            })
        
        self.exchange_info_cache = {}
        self.time_offset = 0  # 바이낸스 서버 시간과의 차이 (ms)
        self._sync_server_time()
        logger.info("BinanceClient 초기화 완료.")

        # 장시간 실행 안정성: 주기적으로 서버 시간 재동기화 (30분 간격)
        try:
            t = threading.Thread(target=self._time_resync_loop, name="binance_time_resync", daemon=True)
            t.start()
        except Exception as e:
            logger.warning(f"시간 재동기화 스레드 시작 실패: {e}")
    
    def _sign_request(self, params: dict) -> str:
        """요청에 서명하고 서명된 쿼리 문자열을 반환합니다."""
        query_string = urllib.parse.urlencode(params)
        m = hmac.new(self.secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        params['signature'] = m.hexdigest()
        return urllib.parse.urlencode(params)
    
    def _sync_server_time(self):
        """바이낸스 서버 시간과 동기화하여 offset 계산"""
        try:
            response = self.session.get(f"{self.base_url}/fapi/v1/time", timeout=5)
            if response.status_code == 200:
                server_time = response.json()['serverTime']
                local_time = int(time.time() * 1000)
                self.time_offset = server_time - local_time
                logger.info(f"바이낸스 서버 시간 동기화 완료. Offset: {self.time_offset}ms")
            else:
                logger.warning(f"서버 시간 동기화 실패: {response.status_code}")
                self.time_offset = 0
        except Exception as e:
            logger.warning(f"서버 시간 동기화 중 오류: {e}")
            self.time_offset = 0

    def _time_resync_loop(self):
        """30분마다 서버 시간 재동기화"""
        try:
            while True:
                time.sleep(1800)  # 30분
                self._sync_server_time()
        except Exception as e:
            logger.warning(f"시간 재동기화 루프 오류: {e}")
    
    def _send_signed_request(self, http_method: str, path: str, params: Optional[dict] = None, 
                            weight_category: str = "general", weight: int = 1) -> Dict[str, Any]:
        """서명된 프라이빗 API 요청을 전송합니다."""
        if not self.api_key or not self.secret_key:
            return {"error": "API 키 또는 시크릿 키가 설정되지 않았습니다."}
        
        rate_limit_manager.wait_for_permission(category=weight_category, weight=weight)
        
        if params is None:
            params = {}
        
        # 안정성 향상: recvWindow 확장 (네트워크 지연 대비)
        params['recvWindow'] = 60000
        
        # -1021 대응을 위한 최대 1회 재시도 로직
        for attempt in range(2):
            try:
                # 매 시도마다 최신 timestamp 재계산
                params['timestamp'] = int(time.time() * 1000) + self.time_offset
                full_url = f"{self.base_url}{path}?{self._sign_request(dict(params))}"
                response = self.session.request(http_method, full_url, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                error_text = e.response.text or ""
                status_code = e.response.status_code
                # Binance 시간 오차 -1021 처리: 서버 시간 재동기화 후 1회 재시도
                if ("-1021" in error_text or "Timestamp for this request is outside of the recvWindow" in error_text) and attempt == 0:
                    logger.warning("-1021 감지: 서버 시간 재동기화 후 재시도합니다.")
                    self._sync_server_time()
                    continue
                logger.error(f"HTTP 오류 발생 ({http_method} {path}): {status_code} - {error_text}")
                return {"error": error_text, "code": status_code}
            except requests.exceptions.RequestException as e:
                logger.error(f"API 요청 중 오류 발생 ({http_method} {path}): {e}")
                return {"error": str(e), "code": -1}
    
    def _send_public_request(self, http_method: str, path: str, params: Optional[dict] = None,
                            weight_category: str = "general", weight: int = 1) -> Dict[str, Any]:
        """서명되지 않은 퍼블릭 API 요청을 전송합니다."""
        rate_limit_manager.wait_for_permission(category=weight_category, weight=weight)
        
        if params is None:
            params = {}
        
        try:
            full_url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
            response = self.session.request(http_method, full_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_details = e.response.text
            status_code = e.response.status_code
            logger.error(f"HTTP 오류 발생 ({http_method} {path}): {status_code} - {error_details}")
            return {"error": error_details, "code": status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 중 오류 발생 ({http_method} {path}): {e}")
            return {"error": str(e), "code": -1}
    
    def get_account_info(self) -> Dict[str, Any]:
        """계좌 정보를 가져옵니다 (잔고, PNL 등)."""
        return self._send_signed_request("GET", "/fapi/v2/account", weight_category="general", weight=5)
    
    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        """특정 심볼의 현재 Mark Price와 Funding Rate 정보를 가져옵니다."""
        params = {'symbol': symbol}
        return self._send_public_request("GET", "/fapi/v1/premiumIndex", params=params, weight_category="general", weight=1)
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500, 
                   start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict[str, Any]:
        """캔들스틱 데이터를 가져옵니다."""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time is not None:
            params['startTime'] = start_time
        if end_time is not None:
            params['endTime'] = end_time
        
        response = self._send_public_request("GET", "/fapi/v1/klines", params=params, weight_category="general", weight=1)
        if "error" not in response:
            return response
        return []
    
    def get_24hr_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """24시간 가격 변동 통계를 가져옵니다. symbol이 없으면 모든 심볼의 데이터를 가져옵니다."""
        params = {}
        if symbol:
            params['symbol'] = symbol
            weight = 1
        else:
            # 모든 심볼 조회 시 weight=40
            weight = 40
        
        response = self._send_public_request("GET", "/fapi/v1/ticker/24hr", params=params, weight_category="general", weight=weight)
        if "error" not in response:
            return response
        return [] if not symbol else {}
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """거래소 정보를 가져옵니다 (심볼 목록, 상태 등)."""
        # exchangeInfo는 weight=1
        response = self._send_public_request("GET", "/fapi/v1/exchangeInfo", weight_category="general", weight=1)
        if "error" not in response:
            return response
        return {"symbols": []}

    def _get_symbol_filters(self, symbol: str) -> Dict[str, Any]:
        """심볼의 필터(LOT_SIZE, MARKET_LOT_SIZE, NOTIONAL 등)를 캐시하여 반환"""
        key = f"filters:{symbol}"
        if key in self.exchange_info_cache:
            return self.exchange_info_cache[key]
        info = self.get_exchange_info()
        for s in info.get("symbols", []):
            if s.get("symbol") == symbol:
                filters = {f.get("filterType"): f for f in s.get("filters", [])}
                self.exchange_info_cache[key] = filters
                return filters
        return {}

    def is_symbol_supported(self, symbol: str) -> Dict[str, Any]:
        """선물 심볼 지원 여부와 필터 기초 정보 반환.

        Returns: { supported: bool, reason: str, filters?: dict }
        """
        try:
            info = self.get_exchange_info()
            for s in info.get("symbols", []):
                if s.get("symbol") == symbol:
                    status = s.get("status")
                    if status != "TRADING":
                        return {"supported": False, "reason": f"status={status}"}
                    filters = {f.get("filterType"): f for f in s.get("filters", [])}
                    return {"supported": True, "reason": "OK", "filters": filters}
            return {"supported": False, "reason": "not_found"}
        except Exception as e:
            return {"supported": False, "reason": f"error:{e}"}

    def _round_qty_by_filters(self, symbol: str, raw_qty: float, price_hint: Optional[float] = None) -> Dict[str, Any]:
        """
        시장가 주문용 수량을 거래 필터에 맞춰 내림 반올림하고 유효성 검사.
        Returns: { ok: bool, qty: float, reason?: str }
        """
        try:
            filters = self._get_symbol_filters(symbol)
            lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE") or {}
            step = float(lot.get("stepSize", 0)) or 0.0
            min_qty = float(lot.get("minQty", 0)) if lot else 0.0
            max_qty = float(lot.get("maxQty", 0)) if lot else 0.0

            qty = float(raw_qty)
            if step > 0:
                # floor to step
                qty = (qty // step) * step
            
            # guard against floating point remnants smaller than step
            if step > 0:
                qty = float(f"{qty:.12f}")

            if qty <= 0 or (min_qty and qty < min_qty):
                return {"ok": False, "reason": f"Quantity below minQty ({qty} < {min_qty})", "stepSize": step, "minQty": min_qty}
            if max_qty and qty > max_qty:
                qty = max_qty

            # notional/minNotional validation
            notional_filter = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
            min_notional = float(notional_filter.get("minNotional", 0)) if notional_filter else 0.0
            near_min = False
            notional = None
            
            if min_notional > 0:
                if not price_hint:
                    # get mark price as a conservative reference
                    mp = self.get_mark_price(symbol)
                    price_hint = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else 0.0
                notional = qty * float(price_hint or 0)
                if notional < min_notional:
                    return {"ok": False, "reason": f"Notional below minNotional ({notional:.8f} < {min_notional})", "stepSize": step, "minQty": min_qty, "minNotional": min_notional, "notional": notional}
                if notional < min_notional * 1.1:
                    near_min = True

            return {"ok": True, "qty": qty, "stepSize": step, "minQty": min_qty, "minNotional": min_notional, "notional": notional, "nearMinNotional": near_min}
        except Exception as e:
            return {"ok": False, "reason": f"filter_check_error: {e}"}
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """레버리지 설정 (바이낸스 선물 API)
        
        Args:
            symbol: 코인 심볼 (예: "BTCUSDT")
            leverage: 레버리지 배수 (1~125)
            
        Returns:
            성공 시:
            {
                "leverage": 10,
                "maxNotionalValue": "1000000",
                "symbol": "BTCUSDT"
            }
            
            실패 시:
            {
                "error": "에러 메시지",
                "code": -4028
            }
        """
        if not 1 <= leverage <= 125:
            logger.error(f"레버리지 범위 오류: {leverage}x (1~125 사이여야 함)")
            return {"error": "레버리지는 1~125 사이여야 합니다.", "code": -1}
        
        params = {
            "symbol": symbol,
            "leverage": leverage
        }
        
        logger.info(f"레버리지 설정 요청: {symbol} → {leverage}x")
        
        # POST /fapi/v1/leverage (Weight = 1)
        response = self._send_signed_request(
            "POST", 
            "/fapi/v1/leverage", 
            params=params,
            weight_category="general",
            weight=1
        )
        
        if "error" not in response:
            logger.info(f"✅ 레버리지 설정 성공: {symbol} → {leverage}x")
        else:
            logger.error(f"❌ 레버리지 설정 실패: {symbol} → {response}")
        
        return response
    
    def get_all_positions(self) -> Dict[str, Any]:
        """모든 포지션 정보 조회 (Position Risk)"""
        return self._send_signed_request("GET", "/fapi/v2/positionRisk", weight_category="general", weight=25)
    
    def set_margin_type(self, symbol: str, isolated: bool = True) -> Dict[str, Any]:
        """
        선물 마진 타입 설정 (심볼별)
        
        Args:
            symbol: 코인 심볼 (예: "BTCUSDT")
            isolated: True면 ISOLATED, False면 CROSSED
        
        Returns:
            API 응답 딕셔너리. 이미 동일한 마진 타입인 경우 바이낸스는 -4046 코드를 반환할 수 있으므로, 이를 정상으로 간주합니다.
        """
        params = {
            "symbol": symbol,
            "marginType": "ISOLATED" if isolated else "CROSSED",
        }
        logger.info(f"마진 타입 설정 요청: {symbol} → {'ISOLATED' if isolated else 'CROSSED'}")
        resp = self._send_signed_request("POST", "/fapi/v1/marginType", params=params, weight_category="general", weight=1)
        
        # 오류이지만 'No need to change margin type.'인 경우 정상으로 처리
        if "error" in resp:
            try:
                import json
                data = json.loads(resp.get("error", "{}"))
                code = data.get("code")
                msg = data.get("msg", "")
                if code == -4046 or "No need to change margin type" in msg:
                    logger.info(f"마진 타입 이미 설정됨: {symbol} → {'ISOLATED' if isolated else 'CROSSED'}")
                    return {"symbol": symbol, "marginType": "ISOLATED" if isolated else "CROSSED", "alreadySet": True}
            except Exception:
                pass
        return resp
    
    def create_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        시장가 주문 생성 (진입)
        
        Args:
            symbol: 코인 심볼 (예: "BTCUSDT")
            side: "BUY" (롱 진입) 또는 "SELL" (숏 진입)
            quantity: 주문 수량 (코인 개수)
            
        Returns:
            주문 결과 딕셔너리
            성공 시:
            {
                "orderId": 123456789,
                "symbol": "BTCUSDT",
                "status": "FILLED",
                "avgPrice": "45000.50",
                "executedQty": "0.1",
                ...
            }
            실패 시:
            {
                "error": "에러 메시지",
                "code": -1234
            }
        """
        if quantity <= 0:
            logger.error(f"주문 수량 오류: {quantity} (양수여야 함)")
            return {"error": f"주문 수량은 0보다 커야 합니다: {quantity}", "code": -1}
        
        # 0) 거래 필터에 맞춰 수량 내림 반올림 및 유효성 검증
        mp = self.get_mark_price(symbol)
        price_hint = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else None
        norm = self._round_qty_by_filters(symbol, quantity, price_hint=price_hint)
        if not norm.get("ok"):
            reason = norm.get("reason", "quantity normalization failed")
            logger.error(f"주문 수량 검증 실패: {symbol} {side} | {reason}")
            return {"error": reason, "code": -1130}
        quantity = norm.get("qty", quantity)

        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity,
            'newOrderRespType': 'FULL'
        }
        
        logger.info(f"시장가 주문 생성 요청: {symbol} {side} {quantity}")
        
        # POST /fapi/v1/order (Weight = 1)
        result = self._send_signed_request(
            "POST",
            "/fapi/v1/order",
            params=params,
            weight_category="general",
            weight=1
        )
        
        if "error" not in result:
            avg_price = result.get('avgPrice', 'N/A')
            executed_qty = result.get('executedQty', 'N/A')
            logger.info(f"✅ 시장가 주문 성공: {symbol} {side} | 수량: {executed_qty} | 평균가: {avg_price}")
        else:
            logger.error(f"❌ 시장가 주문 실패: {symbol} {side} | 오류: {result.get('error')}")
        
        return result
    
    def close_position_market(self, symbol: str, side: str = None) -> Dict[str, Any]:
        """
        특정 심볼의 포지션을 시장가로 청산
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
            side: 포지션 방향 ("BUY" for LONG, "SELL" for SHORT), None이면 자동 판단
        
        Returns:
            주문 결과 딕셔너리
        """
        # 포지션 정보 조회
        positions = self.get_all_positions()
        if "error" in positions:
            return positions
        
        # 해당 심볼의 포지션 찾기
        target_position = None
        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("positionAmt", 0)) != 0:
                target_position = pos
                break
        
        if not target_position:
            return {"error": f"{symbol}에 대한 포지션이 없습니다."}
        
        position_amt = float(target_position.get("positionAmt", 0))
        
        # 포지션 방향 판단
        if side is None:
            side = "SELL" if position_amt > 0 else "BUY"
        
        # 청산 주문 (반대 방향으로 시장가 주문)
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': abs(position_amt),
            'reduceOnly': True,  # 포지션 청산 전용
            'newOrderRespType': 'FULL'
        }
        
        result = self._send_signed_request("POST", "/fapi/v1/order", params=params, weight_category="general", weight=1)
        
        if "error" not in result:
            logger.info(f"포지션 청산 성공: {symbol}, {side}, 수량: {abs(position_amt)}")
        else:
            logger.error(f"포지션 청산 실패: {symbol}, 오류: {result.get('error')}")
        
        return result
    
    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """
        특정 심볼의 모든 미체결 주문 취소
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
        
        Returns:
            API 응답 딕셔너리
            성공 시: {"code": 200, "msg": "The operation of cancel all open order is done."}
            주문 없을 시: {"error": "...", "code": -2011} (주문이 없는 경우도 오류로 반환됨)
        """
        params = {'symbol': symbol}
        logger.info(f"미체결 주문 취소 요청: {symbol}")
        
        result = self._send_signed_request(
            "DELETE",
            "/fapi/v1/allOpenOrders",
            params=params,
            weight_category="general",
            weight=1
        )
        
        if "error" not in result:
            logger.info(f"✅ 미체결 주문 취소 성공: {symbol}")
        else:
            # -2011 (No such order) 등은 정상적인 상황일 수 있음
            logger.warning(f"미체결 주문 취소 응답: {symbol} | {result.get('error')}")
        
        return result
    
    def close_all_positions(self) -> Dict[str, Any]:
        """
        모든 선물 포지션을 시장가로 즉시 청산 (긴급 청산)
        
        Returns:
            청산 결과 딕셔너리
        """
        logger.warning("긴급 포지션 청산 시작: 모든 선물 포지션 시장가 청산")
        
        # 모든 포지션 조회
        positions = self.get_all_positions()
        if "error" in positions:
            logger.error(f"포지션 조회 실패: {positions.get('error')}")
            return positions
        
        closed_positions = []
        errors = []
        
        # 각 포지션 청산
        for pos in positions:
            symbol = pos.get("symbol")
            position_amt = float(pos.get("positionAmt", 0))
            
            # 포지션이 있는 경우만 청산
            if position_amt != 0:
                side = "SELL" if position_amt > 0 else "BUY"
                
                result = self.close_position_market(symbol, side)
                
                if "error" not in result:
                    closed_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "amount": abs(position_amt),
                        "status": "success"
                    })
                else:
                    errors.append({
                        "symbol": symbol,
                        "error": result.get("error")
                    })
        
        if closed_positions:
            logger.info(f"긴급 포지션 청산 완료: {len(closed_positions)}개 포지션 청산 성공")
        if errors:
            logger.error(f"긴급 포지션 청산 오류: {len(errors)}개 포지션 청산 실패")
        
        return {
            "success": len(errors) == 0,
            "closed_count": len(closed_positions),
            "closed_positions": closed_positions,
            "errors": errors
        }
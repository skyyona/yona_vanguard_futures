import os
import time
import hmac
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

from backtesting_backend.api_client.rate_limit_manager import RateLimitManager
from backtesting_backend.core.logger import logger


class BinanceAPIException(Exception):
    pass


class BinanceClient:
    """Minimal async Binance REST client for historical klines (futures).

    This client is intentionally lightweight: it handles signing (when
    needed), rate limiting via RateLimitManager, and paginated kline fetches.
    """

    def __init__(self,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 rate_limit_manager: Optional[RateLimitManager] = None,
                 base_url: Optional[str] = None,
                 timeout: int = 30):
        # load .env if present
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_path = os.path.join(project_root, ".env")
        load_dotenv(env_path)

        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_SECRET_KEY")
        self.rate_limit = rate_limit_manager or RateLimitManager()
        self.base_url = base_url or "https://fapi.binance.com"
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def close(self) -> None:
        await self._client.aclose()

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Binance requires timestamp in milliseconds and HMAC-SHA256 signature
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(sorted(params.items()))
        if not self.api_secret:
            raise BinanceAPIException("API secret is required for signed endpoints")
        signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        return params

    async def _send_request(self, method: str, path: str, params: Dict[str, Any] = None, signed: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        params = params or {}
        if signed:
            params = self._sign(params)

        # Use rate limit manager to throttle requests
        async with self.rate_limit:
            resp = await self._client.request(method, url, params=params)

        if resp.status_code >= 400:
            raise BinanceAPIException(f"Binance API error {resp.status_code}: {resp.text}")
        return resp.json()

    async def get_klines(self, symbol: str, interval: str, start_time: Optional[int] = None,
                         end_time: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch klines from Binance futures endpoint with pagination.

        Returns list of dicts matching Kline model fields.
        """
        path = "/fapi/v1/klines"
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)

        all_klines: List[Dict[str, Any]] = []

        # Log request parameters for debugging empty/timeout responses
        try:
            logger.info("BinanceClient.get_klines request: symbol=%s interval=%s startTime=%s endTime=%s limit=%s",
                        symbol, interval, start_time, end_time, limit)
        except Exception:
            pass

        while True:
            data = await self._send_request("GET", path, params=params, signed=False)
            if not data:
                break

            for item in data:
                k = {
                    "open_time": int(item[0]),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "close_time": int(item[6]),
                    "quote_asset_volume": float(item[7]) if item[7] is not None else None,
                    "number_of_trades": int(item[8]) if item[8] is not None else None,
                    "taker_buy_base_asset_volume": float(item[9]) if item[9] is not None else None,
                    "taker_buy_quote_asset_volume": float(item[10]) if item[10] is not None else None,
                    "ignore": float(item[11]) if item[11] is not None else None,
                    "symbol": symbol,
                    "interval": interval,
                }
                all_klines.append(k)

            # Log page details
            try:
                logger.info("BinanceClient.get_klines: fetched %d items (page), last_open_time=%s", len(data), int(data[-1][0]) if data else None)
            except Exception:
                pass

            if len(data) < limit:
                break

            # paginate: set startTime to last open_time + 1 ms to avoid duplication
            last_open_time = int(data[-1][0])
            params["startTime"] = last_open_time + 1

            # optional: respect user provided end_time
            if end_time is not None and params.get("startTime", 0) > end_time:
                break

        return all_klines

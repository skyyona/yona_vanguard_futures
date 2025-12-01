"""
yona_service.py 파일 끝에 추가할 메서드들

파일 끝 (return [] 이후)에 다음 코드를 추가하세요:
"""

async def analyze_entry_timing(self, symbol: str) -> Dict[str, Any]:
    """
    포지션 진입 타이밍 분석 (간단한 버전)
    실제 바이낸스 데이터를 기반으로 추세 분석과 차트 데이터 제공
    """
    try:
        # 1분봉 데이터 수집
        klines = await self.binance_client.get_klines(symbol=symbol, interval='1m', limit=100)
        
        if not klines or len(klines) < 50:
            return self._get_fallback_analysis(symbol)
        
        # 종가 데이터 추출
        close_prices = [float(k[4]) for k in klines]
        
        # 간단한 EMA 계산
        def ema(prices: List[float], period: int) -> List[float]:
            if len(prices) < period:
                return prices[:]
            k = 2 / (period + 1)
            result = [prices[0]]
            for price in prices[1:]:
                result.append(price * k + result[-1] * (1 - k))
            return result
        
        ema20 = ema(close_prices, 20)
        ema50 = ema(close_prices, 50)
        
        # 현재가
        current_price = close_prices[-1]
        
        # 추세 판단
        if current_price > ema20[-1] > ema50[-1]:
            trend_5m = "상승"
            overall = "상승 추세"
        elif current_price < ema20[-1] < ema50[-1]:
            trend_5m = "하락"
            overall = "하락 추세"
        else:
            trend_5m = "횡보"
            overall = "횡보"
        
        return {
            "symbol": symbol,
            "score": 50,
            "series": {
                "close": close_prices[-50:],
                "ema20": ema20[-50:],
                "ema50": ema50[-50:],
                "vwap": [],
                "bpr": [],
                "vss": []
            },
            "trend_analysis": {
                "5m": {
                    "direction": trend_5m,
                    "strength": 50,
                    "predicted_upside": 0.0,
                    "price_status": {"status": trend_5m}
                },
                "15m": {
                    "direction": trend_5m,
                    "strength": 50,
                    "predicted_upside": 0.0,
                    "price_status": {"status": trend_5m}
                },
                "overall": overall
            },
            "levels": {
                "entry_zone": {},
                "stop": None,
                "tp1": None,
                "tp2": None
            }
        }
        
    except Exception as e:
        self.logger.error(f"진입 타이밍 분석 실패 ({symbol}): {e}")
        return self._get_fallback_analysis(symbol)

def _get_fallback_analysis(self, symbol: str) -> Dict[str, Any]:
    """API 실패 시 기본 분석 데이터"""
    return {
        "symbol": symbol,
        "score": 0,
        "series": {
            "close": [],
            "ema20": [],
            "ema50": [],
            "vwap": [],
            "bpr": [],
            "vss": []
        },
        "trend_analysis": {
            "5m": {
                "direction": "연결중",
                "strength": 0,
                "predicted_upside": 0.0,
                "price_status": {"status": "대기"}
            },
            "15m": {
                "direction": "연결중",
                "strength": 0,
                "predicted_upside": 0.0,
                "price_status": {"status": "대기"}
            },
            "overall": "바이낸스 API 연결 중"
        },
        "levels": {
            "entry_zone": {},
            "stop": None,
            "tp1": None,
            "tp2": None
        }
    }

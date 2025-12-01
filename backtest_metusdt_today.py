"""
METUSDT 오늘(00:00~현재) 백테스트
YONA 알파 전략 시뮬레이션: 진입 조건, 리스크 관리, 손절/익절 검증
"""
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
import statistics

def fetch_klines(symbol: str, interval: str, start_time: int, end_time: int = None, limit: int = 1000) -> List[List]:
    """바이낸스 선물 klines 데이터 조회"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "limit": limit
    }
    if end_time:
        params["endTime"] = end_time
    
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

def ema(values: List[float], period: int) -> List[float]:
    """EMA 계산"""
    if len(values) < period:
        return [values[-1]] * len(values) if values else [0.0]
    
    result = []
    multiplier = 2.0 / (period + 1)
    
    # 첫 EMA는 SMA로 시작
    sma = sum(values[:period]) / period
    result.append(sma)
    
    for i in range(period, len(values)):
        ema_val = (values[i] - result[-1]) * multiplier + result[-1]
        result.append(ema_val)
    
    # 앞부분 채우기
    return [result[0]] * (period - 1) + result

def calculate_signals(klines_1m: List[List], klines_5m: List[List], current_idx: int) -> Dict[str, Any]:
    """
    특정 시점의 진입 신호 계산 (YONA 알파 전략)
    현재(current_idx)까지의 1분봉 데이터를 사용해 신호 산출
    """
    # 현재까지의 데이터만 사용 (미래 데이터 사용 방지)
    data_1m = klines_1m[:current_idx + 1]
    
    if len(data_1m) < 120:
        return {"entry_signals": 0, "reason": "insufficient data", "current_price": 0}
    
    # 최근 120개 1분봉
    recent_120 = data_1m[-120:]
    close_1m = [float(k[4]) for k in recent_120]
    high_1m = [float(k[2]) for k in recent_120]
    low_1m = [float(k[3]) for k in recent_120]
    vol_1m = [float(k[5]) for k in recent_120]
    
    current_price = close_1m[-1]
    
    # EMA 계산
    ema20_1m = ema(close_1m, 20)
    ema50_1m = ema(close_1m, 50)
    ema20_val = ema20_1m[-1]
    ema50_val = ema50_1m[-1]
    
    # VWAP 계산
    typical = [(float(k[2]) + float(k[3]) + float(k[4])) / 3.0 for k in recent_120]
    cum_pv = 0.0
    cum_v = 0.0
    vwap_list = []
    for i in range(len(recent_120)):
        v = max(0.0, vol_1m[i])
        cum_pv += typical[i] * v
        cum_v += v
        vwap_list.append((cum_pv / cum_v) if cum_v > 0 else typical[i])
    vwap_val = vwap_list[-1]
    
    # 5분봉 추세 (최근 50개)
    if len(klines_5m) < 50:
        trend_5m_bullish = False
    else:
        recent_5m = klines_5m[-50:]
        close_5m = [float(k[4]) for k in recent_5m]
        ema20_5m = ema(close_5m, 20)
        ema20_5m_val = ema20_5m[-1]
        current_5m = close_5m[-1]
        
        price_vs_ema = ((current_5m - ema20_5m_val) / ema20_5m_val * 100) if ema20_5m_val > 0 else 0
        
        if current_5m > ema20_5m_val * 1.003:  # 0.3% 이상 상승
            trend_5m = "강상승"
        elif current_5m > ema20_5m_val:
            trend_5m = "상승"
        else:
            trend_5m = "기타"
        
        trend_5m_bullish = trend_5m in ["상승", "강상승"]
    
    # 신호 계산
    entry_signals = 0
    signal_messages = []
    
    # 1. 거래량 급증 (최근 거래량 > 평균 20개 * 3.0)
    recent_volume = vol_1m[-1]
    avg_volume_20 = sum(vol_1m[-20:]) / 20.0 if len(vol_1m) >= 20 else recent_volume
    volume_spike = recent_volume > (avg_volume_20 * 3.0)
    if volume_spike:
        entry_signals += 30
        signal_messages.append("거래량 급증")
    
    # 2. VWAP 돌파
    vwap_break = current_price > vwap_val
    if vwap_break:
        entry_signals += 25
        signal_messages.append("VWAP 돌파")
    
    # 3. 5분 상승 추세
    if trend_5m_bullish:
        entry_signals += 20
        signal_messages.append("5분 상승")
    
    # 4. 24시간 최고가 돌파
    if len(high_1m) >= 1440:
        high_24h = max(high_1m[-1440:])
    else:
        high_24h = max(high_1m)
    high_break = current_price > (high_24h * 1.002)
    if high_break:
        entry_signals += 20
        signal_messages.append("24시간 고점 돌파")
    
    # 5. 연속 상승 (최근 3개 캔들)
    consecutive_green = False
    if len(close_1m) >= 3:
        consecutive_green = all(close_1m[i] > close_1m[i-1] for i in range(-3, 0))
    if consecutive_green:
        entry_signals += 15
        signal_messages.append("연속 상승")
    
    # 진입/손절/목표가 계산
    entry_zone_min = max(ema20_val, vwap_val) * 0.999
    entry_zone_max = max(ema20_val, vwap_val) * 1.001
    
    swing_low = min(low_1m[-20:]) if len(low_1m) >= 20 else current_price * 0.98
    stop_loss = swing_low * 0.998
    
    risk_ratio = (current_price - stop_loss) / current_price if current_price > 0 else 0.02
    tp1 = current_price * (1 + risk_ratio * 1.5)
    tp2 = current_price * (1 + risk_ratio * 3.0)
    
    return {
        "entry_signals": entry_signals,
        "signal_messages": signal_messages,
        "current_price": current_price,
        "entry_zone_min": entry_zone_min,
        "entry_zone_max": entry_zone_max,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "risk_ratio": risk_ratio
    }

def simulate_trading(symbol: str = "METUSDT"):
    """오늘 00:00 UTC부터 현재까지 거래 시뮬레이션"""
    
    # 오늘 00:00 UTC 타임스탬프
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
    start_ts = int(today_start.timestamp() * 1000)
    
    print(f"=== {symbol} 백테스트: {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC ~ 현재 ===\n")
    
    # 1분봉 데이터 (오늘 00:00 ~ 현재)
    klines_1m = fetch_klines(symbol, "1m", start_ts, limit=1500)
    
    # 5분봉 데이터 (최근 50개)
    klines_5m = fetch_klines(symbol, "5m", start_ts - 5 * 60 * 1000 * 100, limit=100)
    
    print(f"수집 데이터: 1분봉 {len(klines_1m)}개, 5분봉 {len(klines_5m)}개\n")
    
    # 거래 변수
    position = None  # {"entry_price": float, "entry_time": str, "stop": float, "tp1": float, "tp2": float, "signals": int}
    trades = []
    
    # 시뮬레이션 시작 (120개 이후부터 분석 가능)
    for i in range(120, len(klines_1m)):
        timestamp = klines_1m[i][0]
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        
        current_close = float(klines_1m[i][4])
        current_high = float(klines_1m[i][2])
        current_low = float(klines_1m[i][3])
        
        # 포지션이 없으면 진입 조건 검사
        if position is None:
            signals = calculate_signals(klines_1m, klines_5m, i)
            
            # 진입 조건: entry_signals >= 70 (진입 권장 이상)
            if signals["entry_signals"] >= 70:
                position = {
                    "entry_price": current_close,
                    "entry_time": dt.strftime('%Y-%m-%d %H:%M:%S'),
                    "entry_timestamp": timestamp,
                    "stop": signals["stop_loss"],
                    "tp1": signals["tp1"],
                    "tp2": signals["tp2"],
                    "signals": signals["entry_signals"],
                    "signal_messages": signals["signal_messages"]
                }
                print(f"✅ 진입: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   가격: {current_close:.4f} USDT")
                print(f"   신호 점수: {signals['entry_signals']}점")
                print(f"   활성 신호: {', '.join(signals['signal_messages'])}")
                print(f"   손절: {signals['stop_loss']:.4f} USDT ({((signals['stop_loss'] - current_close) / current_close * 100):.2f}%)")
                print(f"   목표1: {signals['tp1']:.4f} USDT (+{((signals['tp1'] - current_close) / current_close * 100):.2f}%)")
                print(f"   목표2: {signals['tp2']:.4f} USDT (+{((signals['tp2'] - current_close) / current_close * 100):.2f}%)\n")
        
        # 포지션이 있으면 청산 조건 검사
        else:
            # 손절 히트 (Low가 손절가 이하)
            if current_low <= position["stop"]:
                exit_price = position["stop"]
                profit_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "profit_pct": profit_pct,
                    "reason": "손절"
                })
                
                print(f"❌ 손절: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   청산 가격: {exit_price:.4f} USDT")
                print(f"   수익률: {profit_pct:.2f}%\n")
                
                position = None
            
            # TP1 히트 (High가 TP1 이상) - 50% 청산
            elif current_high >= position["tp1"] and "tp1_hit" not in position:
                exit_price = position["tp1"]
                profit_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                
                # TP1에서 절반 청산 기록
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "profit_pct": profit_pct,
                    "reason": "TP1 (50% 청산)",
                    "partial": 0.5
                })
                
                print(f"✅ TP1 도달 (50% 청산): {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   청산 가격: {exit_price:.4f} USDT")
                print(f"   수익률: {profit_pct:.2f}%")
                print(f"   잔여 포지션: 50% (손절가를 본전으로 이동)\n")
                
                # 손절가를 본전으로 이동
                position["stop"] = position["entry_price"]
                position["tp1_hit"] = True
            
            # TP2 히트 (High가 TP2 이상) - 나머지 청산
            elif current_high >= position["tp2"]:
                exit_price = position["tp2"]
                profit_pct = (exit_price - position["entry_price"]) / position["entry_price"] * 100
                
                partial = 0.5 if "tp1_hit" in position else 1.0
                
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "profit_pct": profit_pct,
                    "reason": f"TP2 ({'50%' if partial == 0.5 else '100%'} 청산)",
                    "partial": partial
                })
                
                print(f"🎯 TP2 도달 (나머지 청산): {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   청산 가격: {exit_price:.4f} USDT")
                print(f"   수익률: {profit_pct:.2f}%\n")
                
                position = None
    
    # 포지션이 남아있으면 현재가로 청산
    if position is not None:
        current_price = float(klines_1m[-1][4])
        current_time = datetime.fromtimestamp(klines_1m[-1][0] / 1000, tz=timezone.utc)
        profit_pct = (current_price - position["entry_price"]) / position["entry_price"] * 100
        
        partial = 0.5 if "tp1_hit" in position else 1.0
        
        trades.append({
            "entry_time": position["entry_time"],
            "exit_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
            "entry_price": position["entry_price"],
            "exit_price": current_price,
            "profit_pct": profit_pct,
            "reason": f"미청산 ({'50%' if partial == 0.5 else '100%'} 포지션)",
            "partial": partial
        })
        
        print(f"⏸️  미청산 포지션: {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"   현재가: {current_price:.4f} USDT")
        print(f"   미실현 수익률: {profit_pct:.2f}%\n")
    
    # 결과 집계
    print("=" * 80)
    print("📊 백테스트 결과 요약\n")
    
    if not trades:
        print("❌ 진입 조건을 충족한 시점이 없습니다.")
        print(f"   (진입 조건: 신호 점수 70점 이상 = 진입 권장 이상)")
        return
    
    total_profit = 0.0
    realized_trades = [t for t in trades if "미청산" not in t["reason"]]
    
    for idx, trade in enumerate(trades, 1):
        partial = trade.get("partial", 1.0)
        weighted_profit = trade["profit_pct"] * partial
        total_profit += weighted_profit
        
        print(f"거래 #{idx}:")
        print(f"  진입: {trade['entry_time']} @ {trade['entry_price']:.4f} USDT")
        print(f"  청산: {trade['exit_time']} @ {trade['exit_price']:.4f} USDT")
        print(f"  사유: {trade['reason']}")
        print(f"  수익률: {trade['profit_pct']:.2f}% (가중: {weighted_profit:.2f}%)")
        print()
    
    print(f"총 거래 횟수: {len(realized_trades)}회 (실현)")
    if len(trades) > len(realized_trades):
        print(f"미청산 포지션: {len(trades) - len(realized_trades)}개")
    
    print(f"\n🎯 총 수익률: {total_profit:.2f}%")
    
    if realized_trades:
        avg_profit = statistics.mean([t["profit_pct"] for t in realized_trades])
        print(f"   평균 수익률: {avg_profit:.2f}%")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    simulate_trading("METUSDT")

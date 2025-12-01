"""
ESPOTUSDT 오늘(00:00~현재) 백테스트
고도화된 YONA 알파 전략 (170점 만점): 진입 조건, 리스크 관리, 손절/익절 검증
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

def rsi(prices: List[float], period: int = 14) -> List[float]:
    """RSI 계산 (Wilder's Smoothing)"""
    if len(prices) < period + 1:
        return [50.0] * len(prices)
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [max(0, d) for d in deltas]
    losses = [max(0, -d) for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi_values = [50.0] * period
    
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi_val = 100
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100 - (100 / (1 + rs))
        
        rsi_values.append(rsi_val)
    
    return rsi_values

def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
    """MACD 계산"""
    if len(prices) < slow + signal:
        return {"macd": [0.0] * len(prices), "signal": [0.0] * len(prices), "histogram": [0.0] * len(prices)}
    
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(prices))]
    signal_line = ema(macd_line, signal)
    histogram = [macd_line[i] - signal_line[i] for i in range(len(macd_line))]
    
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

def calculate_signals_advanced(klines_1m: List[List], klines_5m: List[List], current_idx: int) -> Dict[str, Any]:
    """
    특정 시점의 진입 신호 계산 (고도화된 YONA 알파 전략 - 170점 만점)
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
    
    # RSI 계산
    rsi_1m = rsi(close_1m, 14)
    rsi_current = rsi_1m[-1]
    
    # MACD 계산
    macd_result = macd(close_1m, 12, 26, 9)
    macd_line = macd_result["macd"][-1]
    signal_line = macd_result["signal"][-1]
    histogram = macd_result["histogram"][-1]
    
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
        is_strong_trend = trend_5m == "강상승"
    
    # === 신호 계산 (170점 만점) ===
    entry_signals = 0
    signal_messages = []
    
    # === 기존 5개 신호 (110점) ===
    
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
    
    # === 추가 4개 핵심 신호 (60점) ===
    
    # 6. 3분봉 추세 확인 (20점) ⭐ 핵심
    # EMA60으로 근사 (실제로는 3분봉 데이터 필요)
    if ema50_val > ema20_val * 0.998:  # 중기 추세도 상승
        entry_signals += 20
        signal_messages.append("3분 상승")
    
    # 7. 음봉 에너지 소멸 (15점) ⭐ 핵심
    # 최근 10개 캔들의 양봉/음봉 거래량 비교
    if len(recent_120) >= 10:
        last_10_candles = recent_120[-10:]
        bull_volume = 0.0
        bear_volume = 0.0
        for k in last_10_candles:
            open_price = float(k[1])
            close_price = float(k[4])
            volume = float(k[5])
            
            if close_price > open_price:  # 양봉
                bull_volume += volume
            else:  # 음봉
                bear_volume += volume
        
        if bull_volume > bear_volume * 2.0:  # 양봉이 2배 이상
            entry_signals += 15
            signal_messages.append("음봉 에너지 소멸")
    
    # 8. MACD 골든크로스 (15점) ⭐ 핵심
    if macd_line > signal_line and histogram > 0:
        entry_signals += 15
        signal_messages.append("MACD 골든크로스")
    
    # 9. RSI 과매도 반등 (10점) ⭐ 핵심
    if 20 < rsi_current < 35:
        entry_signals += 10
        signal_messages.append("RSI 과매도 반등")
    elif rsi_current > 70:
        # 과매수 경고 (감점)
        entry_signals -= 10
        signal_messages.append("⚠️ RSI 과매수")
    
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
        "risk_ratio": risk_ratio,
        "rsi": rsi_current,
        "macd": macd_line,
        "macd_signal": signal_line
    }

def simulate_trading(symbol: str = "ESPORTSUSDT", debug: bool = False):
    """오늘 00:00 UTC부터 현재까지 거래 시뮬레이션 (고도화 버전)"""
    
    # 오늘 00:00 UTC
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
    start_ts = int(today_start.timestamp() * 1000)
    
    print(f"\n{'='*80}")
    print(f"🔬 {symbol} 백테스트 (고도화 전략 - 170점 만점)")
    print(f"{'='*80}")
    print(f"📅 기간: {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC ~ 현재")
    print(f"⏰ 시작 시간: {start_ts}")
    print(f"\n{'='*80}\n")
    
    # 1분봉 데이터 (1440개 = 24시간)
    print("📊 1분봉 데이터 수집 중...")
    klines_1m = fetch_klines(symbol, "1m", start_ts, limit=1500)
    print(f"✅ 1분봉 {len(klines_1m)}개 수집 완료")
    
    # 5분봉 데이터
    print("📊 5분봉 데이터 수집 중...")
    klines_5m = fetch_klines(symbol, "5m", start_ts, limit=300)
    print(f"✅ 5분봉 {len(klines_5m)}개 수집 완료\n")
    
    if len(klines_1m) < 120:
        print("❌ 데이터 부족 (최소 120개 필요)")
        return
    
    # 거래 시뮬레이션
    positions = []
    current_position = None
    initial_capital = 1000.0  # 초기 자본 1000 USDT
    capital = initial_capital
    
    print(f"💰 초기 자본: {initial_capital:.2f} USDT\n")
    print(f"{'='*80}")
    print("🔍 거래 스캔 시작...")
    print(f"{'='*80}\n")
    
    # 최고 점수 추적
    max_score = 0
    max_score_info = None
    
    # 120개 이후부터 스캔 (EMA 계산을 위해)
    for i in range(120, len(klines_1m)):
        timestamp = klines_1m[i][0]
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        
        # 신호 계산
        signals = calculate_signals_advanced(klines_1m, klines_5m, i)
        current_price = signals["current_price"]
        entry_score = signals["entry_signals"]
        
        # 최고 점수 추적
        if entry_score > max_score:
            max_score = entry_score
            max_score_info = {
                "time": dt,
                "score": entry_score,
                "price": current_price,
                "messages": signals["signal_messages"]
            }
        
        # 디버그 모드: 100점 이상 신호 출력
        if debug and entry_score >= 100:
            print(f"⏰ {dt.strftime('%H:%M')} | {entry_score}점 | ${current_price:.6f} | {', '.join(signals['signal_messages'])}")
        
        # 포지션 없을 때: 진입 조건 확인
        if current_position is None:
            # 120점 이상: 진입 권장 (테스트용)
            # 130점 이상: 진입 권장 (원래)
            # 160점 이상: 즉시 진입
            if entry_score >= 120:  # 테스트: 70% 이상
                # 진입
                entry_price = current_price
                position_size = capital / entry_price
                stop_loss = signals["stop_loss"]
                tp1 = signals["tp1"]
                tp2 = signals["tp2"]
                
                current_position = {
                    "entry_idx": i,
                    "entry_time": dt,
                    "entry_price": entry_price,
                    "position_size": position_size,
                    "stop_loss": stop_loss,
                    "tp1": tp1,
                    "tp2": tp2,
                    "capital_at_entry": capital,
                    "entry_score": entry_score,
                    "signal_messages": signals["signal_messages"]
                }
                
                signal_level = "🚀 즉시 진입" if entry_score >= 160 else "✅ 진입 권장"
                print(f"\n{'─'*80}")
                print(f"📈 {signal_level}: {entry_score}점/170점 ({entry_score/170*100:.1f}%)")
                print(f"{'─'*80}")
                print(f"⏰ 시간: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"💵 진입가: ${entry_price:.6f}")
                print(f"📊 포지션: {position_size:.2f} {symbol.replace('USDT', '')}")
                print(f"🛑 손절가: ${stop_loss:.6f} ({((stop_loss - entry_price) / entry_price * 100):.2f}%)")
                print(f"🎯 TP1: ${tp1:.6f} ({((tp1 - entry_price) / entry_price * 100):.2f}%)")
                print(f"🎯 TP2: ${tp2:.6f} ({((tp2 - entry_price) / entry_price * 100):.2f}%)")
                print(f"📋 신호: {', '.join(signals['signal_messages'])}")
                print(f"{'─'*80}")
        
        # 포지션 있을 때: 청산 조건 확인
        else:
            entry_price = current_position["entry_price"]
            stop_loss = current_position["stop_loss"]
            tp1 = current_position["tp1"]
            tp2 = current_position["tp2"]
            position_size = current_position["position_size"]
            
            # 손절 확인
            if current_price <= stop_loss:
                # 손절
                pnl = (current_price - entry_price) * position_size
                pnl_percent = (current_price - entry_price) / entry_price * 100
                capital += pnl
                
                print(f"\n{'─'*80}")
                print(f"🛑 손절 청산")
                print(f"{'─'*80}")
                print(f"⏰ 청산 시간: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"💵 청산가: ${current_price:.6f}")
                print(f"📊 손익: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
                print(f"💰 잔고: ${capital:.2f} USDT")
                print(f"{'─'*80}")
                
                positions.append({
                    "entry_time": current_position["entry_time"],
                    "exit_time": dt,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "result": "손절",
                    "entry_score": current_position["entry_score"]
                })
                current_position = None
            
            # TP1 달성 (50% 청산)
            elif current_price >= tp1 and current_position.get("tp1_hit", False) == False:
                # TP1에서 50% 청산
                half_size = position_size * 0.5
                pnl = (current_price - entry_price) * half_size
                pnl_percent = (current_price - entry_price) / entry_price * 100
                capital += pnl
                
                print(f"\n{'─'*80}")
                print(f"🎯 TP1 달성 (50% 청산)")
                print(f"{'─'*80}")
                print(f"⏰ 청산 시간: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"💵 청산가: ${current_price:.6f}")
                print(f"📊 손익: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
                print(f"💰 잔고: ${capital:.2f} USDT")
                print(f"📈 남은 포지션: 50% (TP2 대기)")
                print(f"{'─'*80}")
                
                current_position["tp1_hit"] = True
                current_position["position_size"] = half_size  # 남은 50%
            
            # TP2 달성 (나머지 50% 청산)
            elif current_price >= tp2:
                # TP2에서 나머지 청산
                remaining_size = current_position["position_size"]
                pnl = (current_price - entry_price) * remaining_size
                pnl_percent = (current_price - entry_price) / entry_price * 100
                capital += pnl
                
                print(f"\n{'─'*80}")
                print(f"🎯 TP2 달성 (나머지 50% 청산)")
                print(f"{'─'*80}")
                print(f"⏰ 청산 시간: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"💵 청산가: ${current_price:.6f}")
                print(f"📊 손익: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
                print(f"💰 잔고: ${capital:.2f} USDT")
                print(f"{'─'*80}")
                
                # TP1과 TP2 합산 기록
                if current_position.get("tp1_hit", False):
                    # TP1 이미 기록됨, TP2만 추가
                    total_pnl_percent = (tp2 - entry_price) / entry_price * 100 * 0.5 + (tp1 - entry_price) / entry_price * 100 * 0.5
                else:
                    # TP1 없이 바로 TP2
                    total_pnl_percent = pnl_percent
                
                positions.append({
                    "entry_time": current_position["entry_time"],
                    "exit_time": dt,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "pnl": (current_price - entry_price) * (position_size if not current_position.get("tp1_hit") else position_size * 2),  # 전체 수익
                    "pnl_percent": total_pnl_percent,
                    "result": "익절 (TP2)",
                    "entry_score": current_position["entry_score"]
                })
                current_position = None
    
    # 미청산 포지션 처리
    if current_position is not None:
        final_price = float(klines_1m[-1][4])
        entry_price = current_position["entry_price"]
        position_size = current_position["position_size"]
        pnl = (final_price - entry_price) * position_size
        pnl_percent = (final_price - entry_price) / entry_price * 100
        capital += pnl
        
        print(f"\n{'─'*80}")
        print(f"⏸️ 미청산 포지션 (현재가 기준 평가)")
        print(f"{'─'*80}")
        print(f"💵 현재가: ${final_price:.6f}")
        print(f"📊 평가 손익: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
        print(f"💰 평가 잔고: ${capital:.2f} USDT")
        print(f"{'─'*80}")
        
        positions.append({
            "entry_time": current_position["entry_time"],
            "exit_time": datetime.now(timezone.utc),
            "entry_price": entry_price,
            "exit_price": final_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "result": "미청산",
            "entry_score": current_position["entry_score"]
        })
    
    # 결과 요약
    print(f"\n{'='*80}")
    print(f"📊 백테스트 결과 요약 ({symbol})")
    print(f"{'='*80}\n")
    
    # 최고 점수 정보 출력
    if max_score_info:
        print(f"🏆 최고 진입 점수:")
        print(f"  • 시간: {max_score_info['time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"  • 점수: {max_score_info['score']}점/170점 ({max_score_info['score']/170*100:.1f}%)")
        print(f"  • 가격: ${max_score_info['price']:.6f}")
        print(f"  • 신호: {', '.join(max_score_info['messages'])}")
        print(f"")
    
    print(f"💰 초기 자본: ${initial_capital:.2f} USDT")
    print(f"💰 최종 잔고: ${capital:.2f} USDT")
    print(f"📈 총 손익: ${capital - initial_capital:.2f} USDT ({(capital - initial_capital) / initial_capital * 100:.2f}%)")
    print(f"\n📊 거래 통계:")
    print(f"  • 총 거래 횟수: {len(positions)}회")
    
    if positions:
        winning_trades = [p for p in positions if p["pnl"] > 0]
        losing_trades = [p for p in positions if p["pnl"] < 0]
        
        print(f"  • 수익 거래: {len(winning_trades)}회")
        print(f"  • 손실 거래: {len(losing_trades)}회")
        print(f"  • 승률: {len(winning_trades) / len(positions) * 100:.1f}%")
        
        if winning_trades:
            avg_win = statistics.mean([p["pnl_percent"] for p in winning_trades])
            print(f"  • 평균 수익률: {avg_win:.2f}%")
        
        if losing_trades:
            avg_loss = statistics.mean([p["pnl_percent"] for p in losing_trades])
            print(f"  • 평균 손실률: {avg_loss:.2f}%")
        
        avg_score = statistics.mean([p["entry_score"] for p in positions])
        print(f"  • 평균 진입 점수: {avg_score:.1f}점/170점 ({avg_score/170*100:.1f}%)")
        
        print(f"\n📋 거래 내역:")
        for idx, pos in enumerate(positions, 1):
            result_icon = "✅" if pos["pnl"] > 0 else "❌" if pos["pnl"] < 0 else "⏸️"
            print(f"  {idx}. {result_icon} {pos['entry_time'].strftime('%H:%M')} → {pos['exit_time'].strftime('%H:%M')} | "
                  f"${pos['entry_price']:.6f} → ${pos['exit_price']:.6f} | "
                  f"{pos['pnl_percent']:+.2f}% ({pos['entry_score']}점) | {pos['result']}")
    
    print(f"\n{'='*80}\n")
    
    return {
        "initial_capital": initial_capital,
        "final_capital": capital,
        "total_pnl": capital - initial_capital,
        "total_pnl_percent": (capital - initial_capital) / initial_capital * 100,
        "total_trades": len(positions),
        "winning_trades": len([p for p in positions if p["pnl"] > 0]),
        "losing_trades": len([p for p in positions if p["pnl"] < 0]),
        "positions": positions
    }

if __name__ == "__main__":
    result = simulate_trading("ESPORTSUSDT", debug=False)

"""바이낸스 선물 거래 코인 심볼 개수 확인"""
from backend.api_client.binance_client import BinanceClient

def main():
    client = BinanceClient()
    
    print("=" * 60)
    print("바이낸스 선물 거래 코인 심볼 검색 결과")
    print("=" * 60)
    
    # 24시간 티커 데이터 조회
    print("\n[1단계] 바이낸스 API에서 24시간 티커 데이터 조회 중...")
    ticker_data = client.get_24hr_ticker()
    
    if isinstance(ticker_data, dict) and "error" in ticker_data:
        print(f"❌ 오류 발생: {ticker_data['error']}")
        return
    
    print(f"✅ API 응답 성공")
    print(f"\n[2단계] 데이터 분석 중...")
    
    # 전체 심볼 수
    total_symbols = len(ticker_data)
    print(f"\n📊 총 심볼 수: {total_symbols}개")
    
    # USDT 선물만 필터링
    usdt_symbols = [t for t in ticker_data if t.get("symbol", "").endswith("USDT")]
    print(f"📊 USDT 선물 심볼 수: {len(usdt_symbols)}개")
    
    # 기타 선물 (BUSD 등)
    other_symbols = [t for t in ticker_data if not t.get("symbol", "").endswith("USDT")]
    if other_symbols:
        print(f"📊 기타 선물 심볼 수: {len(other_symbols)}개")
        # 기타 심볼 종류 확인
        other_types = set()
        for t in other_symbols[:10]:
            symbol = t.get("symbol", "")
            if symbol.endswith("BUSD"):
                other_types.add("BUSD")
            elif "_" in symbol:
                other_types.add("_PERP")
            else:
                other_types.add("기타")
        if other_types:
            print(f"   종류: {', '.join(other_types)}")
    
    # 상승률 기준 정렬
    print(f"\n[3단계] 상위 10개 심볼 (24시간 상승률 기준)")
    print("-" * 60)
    sorted_data = sorted(usdt_symbols, key=lambda x: float(x.get("priceChangePercent", 0)), reverse=True)[:10]
    
    for i, item in enumerate(sorted_data, 1):
        symbol = item.get("symbol", "")
        change_percent = float(item.get("priceChangePercent", 0))
        volume = float(item.get("quoteVolume", 0))
        print(f"{i:2d}. {symbol:15s} {change_percent:+7.2f}%  (거래량: ${volume:,.0f})")
    
    # 하락률 기준 정렬
    print(f"\n[4단계] 하위 10개 심볼 (24시간 하락률 기준)")
    print("-" * 60)
    sorted_data_desc = sorted(usdt_symbols, key=lambda x: float(x.get("priceChangePercent", 0)))[:10]
    
    for i, item in enumerate(sorted_data_desc, 1):
        symbol = item.get("symbol", "")
        change_percent = float(item.get("priceChangePercent", 0))
        volume = float(item.get("quoteVolume", 0))
        print(f"{i:2d}. {symbol:15s} {change_percent:+7.2f}%  (거래량: ${volume:,.0f})")
    
    # 상승률 분포
    print(f"\n[5단계] 상승률 분포 분석")
    print("-" * 60)
    
    surge_count = len([t for t in usdt_symbols if float(t.get("priceChangePercent", 0)) >= 10])
    up_count = len([t for t in usdt_symbols if 3 <= float(t.get("priceChangePercent", 0)) < 10])
    neutral_count = len([t for t in usdt_symbols if -2 <= float(t.get("priceChangePercent", 0)) < 3])
    down_count = len([t for t in usdt_symbols if -5 <= float(t.get("priceChangePercent", 0)) < -2])
    crash_count = len([t for t in usdt_symbols if float(t.get("priceChangePercent", 0)) < -5])
    
    print(f"🔥 급등 (+10% 이상):     {surge_count:3d}개 ({surge_count/len(usdt_symbols)*100:5.1f}%)")
    print(f"📈 지속 상승 (+3~10%):   {up_count:3d}개 ({up_count/len(usdt_symbols)*100:5.1f}%)")
    print(f"➡️  횡보 (-2~+3%):        {neutral_count:3d}개 ({neutral_count/len(usdt_symbols)*100:5.1f}%)")
    print(f"📉 지속 하락 (-5~-2%):   {down_count:3d}개 ({down_count/len(usdt_symbols)*100:5.1f}%)")
    print(f"💥 급락 (-5% 이하):      {crash_count:3d}개 ({crash_count/len(usdt_symbols)*100:5.1f}%)")
    
    print("\n" + "=" * 60)
    print(f"✅ 우리 앱이 검색하는 USDT 선물 심볼: {len(usdt_symbols)}개")
    print("=" * 60)

if __name__ == "__main__":
    main()

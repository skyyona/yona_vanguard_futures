"""신규 상장 코인 표기 테스트"""
import asyncio
import datetime as dt
from backend.api_client.binance_client import BinanceClient

async def main():
    print("=" * 80)
    print("신규 상장 코인 표기 테스트 - 'new N일' 형식")
    print("=" * 80)
    
    client = BinanceClient()
    
    # exchangeInfo 조회
    print("\n[1단계] 바이낸스 exchangeInfo API 조회 중...")
    response = client._send_public_request(
        "GET",
        "/fapi/v1/exchangeInfo",
        weight_category="general",
        weight=1
    )
    
    if isinstance(response, dict) and "error" in response:
        print(f"❌ 오류 발생: {response['error']}")
        return
    
    symbols_data = response.get("symbols", [])
    print(f"✅ 총 {len(symbols_data)}개 심볼 정보 조회 완료")
    
    # onboardDate가 있는 USDT 선물 심볼 필터링
    print("\n[2단계] 신규 상장 코인 분석 중...")
    
    symbol_onboard_dates = {}
    for symbol_info in symbols_data:
        symbol = symbol_info.get("symbol", "")
        onboard_date = symbol_info.get("onboardDate", 0)
        
        if symbol.endswith("USDT") and onboard_date > 0:
            symbol_onboard_dates[symbol] = onboard_date
    
    print(f"✅ onboardDate 정보가 있는 USDT 선물: {len(symbol_onboard_dates)}개")
    
    # 경과일 계산 및 신규 상장 코인 분류
    current_time = dt.datetime.utcnow()
    new_listings = []
    
    for symbol, onboard_date in symbol_onboard_dates.items():
        listing_time = dt.datetime.fromtimestamp(onboard_date / 1000)
        days_diff = (current_time - listing_time).days
        
        if days_diff <= 30:  # 30일 이내 상장 코인
            new_listings.append({
                "symbol": symbol,
                "days": days_diff,
                "listing_date": listing_time.strftime("%Y-%m-%d %H:%M:%S")
            })
    
    # 경과일 순으로 정렬 (최신 상장 순)
    new_listings.sort(key=lambda x: x["days"])
    
    print(f"\n[3단계] 신규 상장 코인 (30일 이내): {len(new_listings)}개")
    print("-" * 80)
    
    if new_listings:
        print(f"{'순번':<6} {'심볼':<15} {'표기':<20} {'경과일':<10} {'상장일시'}")
        print("-" * 80)
        
        for i, coin in enumerate(new_listings[:20], 1):  # 상위 20개만 표시
            symbol = coin["symbol"]
            days = coin["days"]
            listing_date = coin["listing_date"]
            
            # 'new N일' 형식으로 표기
            display_text = f"new {days}일"
            
            print(f"{i:<6} {symbol:<15} {display_text:<20} {days:<10} {listing_date}")
    else:
        print("⚠️ 현재 30일 이내 신규 상장 코인이 없습니다.")
    
    # 24시간 티커 조회하여 실제 랭킹 데이터 구조 확인
    print("\n[4단계] 실제 랭킹 데이터 구조 테스트")
    print("-" * 80)
    
    ticker_data = client.get_24hr_ticker()
    
    if isinstance(ticker_data, list) and len(ticker_data) > 0:
        # 신규 상장 코인 중 하나를 선택하여 완전한 데이터 구조 출력
        if new_listings:
            test_symbol = new_listings[0]["symbol"]
            test_days = new_listings[0]["days"]
            
            # 해당 심볼의 티커 찾기
            test_ticker = None
            for ticker in ticker_data:
                if ticker.get("symbol") == test_symbol:
                    test_ticker = ticker
                    break
            
            if test_ticker:
                change_percent = float(test_ticker.get("priceChangePercent", 0.0))
                
                # 신호 상태 판단
                if change_percent > 15:
                    signal_status = "STRONG_BUY"
                elif change_percent < -10:
                    signal_status = "STRONG_DECLINE"
                else:
                    signal_status = "NORMAL"
                
                # 표기 텍스트
                if signal_status == "STRONG_DECLINE":
                    display_text = "하락"
                elif test_days <= 30:
                    display_text = f"new {test_days}일"
                else:
                    display_text = ""
                
                print(f"\n테스트 심볼: {test_symbol}")
                print(f"  - 상장 후 경과: {test_days}일")
                print(f"  - 24시간 변화: {change_percent:+.2f}%")
                print(f"  - 신호 상태: {signal_status}")
                print(f"  - GUI 표기: '{display_text}'")
                print(f"  - 배경색: {'밝은 청록색 (#b9f2f9)' if test_days <= 30 else '없음'}")
    
    print("\n" + "=" * 80)
    print("✅ 신규 상장 코인 표기 로직 테스트 완료")
    print("=" * 80)
    print("\n📋 GUI 표기 규칙:")
    print("  • 상장 후 30일 이내: 'new N일' 표기 + 밝은 청록색 배경")
    print("  • STRONG_DECLINE 신호: '하락' 표기 + 어두운 회색 배경")
    print("  • 30일 초과: 표기 없음")

if __name__ == "__main__":
    asyncio.run(main())

"""바이낸스 API 연결 테스트"""
from backend.api_client.binance_client import BinanceClient
import json

print("=" * 60)
print("바이낸스 API 연결 테스트")
print("=" * 60)

# 1. 클라이언트 초기화
bc = BinanceClient()
print(f"\n✅ BinanceClient 초기화 완료")
print(f"   - Base URL: {bc.base_url}")
print(f"   - API Key: {bc.api_key[:20]}..." if bc.api_key else "   - API Key: 없음")

# 2. 계좌 정보 조회 (프라이빗 API)
print("\n" + "=" * 60)
print("1. 계좌 정보 조회 (프라이빗 API)")
print("=" * 60)
account_info = bc.get_account_info()
if "error" in account_info:
    print(f"❌ 계좌 정보 조회 실패: {account_info.get('error')}")
    print(f"   - 에러 코드: {account_info.get('code')}")
else:
    print(f"✅ 계좌 정보 조회 성공")
    print(f"   - 총 자산: {account_info.get('totalWalletBalance', 0)} USDT")
    print(f"   - 가용 자산: {account_info.get('availableBalance', 0)} USDT")
    print(f"   - 미실현 손익: {account_info.get('totalUnrealizedProfit', 0)} USDT")

# 3. Mark Price 조회 (퍼블릭 API)
print("\n" + "=" * 60)
print("2. Mark Price 조회 (퍼블릭 API)")
print("=" * 60)
mark_price = bc.get_mark_price("BTCUSDT")
if "error" in mark_price:
    print(f"❌ Mark Price 조회 실패: {mark_price.get('error')}")
else:
    print(f"✅ Mark Price 조회 성공")
    print(f"   - 심볼: {mark_price.get('symbol')}")
    print(f"   - Mark Price: {mark_price.get('markPrice')}")
    print(f"   - Funding Rate: {mark_price.get('lastFundingRate')}")

# 4. 캔들스틱 데이터 조회 (퍼블릭 API)
print("\n" + "=" * 60)
print("3. 캔들스틱 데이터 조회 (퍼블릭 API)")
print("=" * 60)
klines = bc.get_klines("BTCUSDT", "1m", limit=5)
if isinstance(klines, dict) and "error" in klines:
    print(f"❌ 캔들스틱 조회 실패: {klines.get('error')}")
else:
    print(f"✅ 캔들스틱 조회 성공 ({len(klines)}개 데이터)")
    if len(klines) > 0:
        latest = klines[-1]
        print(f"   - 최신 캔들:")
        print(f"     * 시작: {latest[0]}")
        print(f"     * 시가: {latest[1]}")
        print(f"     * 고가: {latest[2]}")
        print(f"     * 저가: {latest[3]}")
        print(f"     * 종가: {latest[4]}")
        print(f"     * 거래량: {latest[5]}")

# 5. 포지션 정보 조회 (프라이빗 API)
print("\n" + "=" * 60)
print("4. 포지션 정보 조회 (프라이빗 API)")
print("=" * 60)
positions = bc.get_all_positions()
if "error" in positions:
    print(f"❌ 포지션 조회 실패: {positions.get('error')}")
else:
    print(f"✅ 포지션 조회 성공 ({len(positions)}개 심볼)")
    active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
    if active_positions:
        print(f"   - 활성 포지션: {len(active_positions)}개")
        for pos in active_positions[:3]:  # 최대 3개만 출력
            print(f"     * {pos.get('symbol')}: {pos.get('positionAmt')} @ {pos.get('entryPrice')}")
    else:
        print(f"   - 활성 포지션: 없음")

print("\n" + "=" * 60)
print("테스트 완료")
print("=" * 60)

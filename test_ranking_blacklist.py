"""
실시간 랭킹리스트 블랙리스트 기능 테스트
- ALPACAUSDT 블랙리스트 추가 시 즉시 랭킹에서 제거 확인
- ALPACAUSDT 블랙리스트 해지 시 즉시 랭킹에 복귀 확인
"""
import asyncio
import websockets
import json
import requests
import time

BASE_URL = "http://localhost:8200"
WS_URL = "ws://localhost:8200/ws"

def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f" {title}")
        print("=" * 70)

async def test_blacklist_ranking():
    print_separator("실시간 랭킹리스트 블랙리스트 기능 테스트")
    
    # 1. WebSocket 연결
    print("\n📡 WebSocket 연결 중...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✅ WebSocket 연결 성공")
            
            # START 명령 전송
            print("\n📤 START 명령 전송...")
            await websocket.send(json.dumps({"action": "start"}))
            
            # 초기 랭킹 수신 대기
            print("\n⏳ 초기 랭킹 데이터 수신 대기...")
            initial_ranking = None
            for _ in range(10):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    if data.get("type") == "RANKING_UPDATE":
                        initial_ranking = data.get("data", [])
                        break
                except asyncio.TimeoutError:
                    continue
            
            if not initial_ranking:
                print("❌ 초기 랭킹 데이터를 받지 못했습니다.")
                return
            
            print(f"\n✅ 초기 랭킹 데이터 수신: {len(initial_ranking)}개 심볼")
            
            # 상위 10개 표시
            print("\n📊 상위 10개 랭킹:")
            for i, item in enumerate(initial_ranking[:10], 1):
                symbol = item.get("symbol")
                change = item.get("change_percent", 0)
                print(f"  {i:2d}. {symbol:15s} {change:>8.2f}%")
            
            # ALPACAUSDT 찾기
            alpaca_in_ranking = any(item.get("symbol") == "ALPACAUSDT" for item in initial_ranking)
            print(f"\n🔍 ALPACAUSDT 랭킹 포함 여부: {'✅ 포함됨' if alpaca_in_ranking else '❌ 없음'}")
            
            if not alpaca_in_ranking:
                print("⚠️  ALPACAUSDT가 초기 랭킹에 없습니다. (SETTLING 상태일 가능성)")
                print("    다른 심볼로 테스트를 진행합니다...")
                test_symbol = initial_ranking[0].get("symbol") if initial_ranking else "BTCUSDT"
            else:
                test_symbol = "ALPACAUSDT"
            
            print(f"\n🎯 테스트 대상 심볼: {test_symbol}")
            
            # ===== 테스트 1: 블랙리스트 추가 =====
            print_separator("테스트 1: 블랙리스트 추가 → 랭킹에서 즉시 제거")
            
            print(f"\n📤 {test_symbol}를 블랙리스트에 추가 중...")
            response = requests.post(
                f"{BASE_URL}/api/v1/live/blacklist/add",
                json={"symbols": [test_symbol]}
            )
            
            if response.status_code == 200:
                print(f"✅ 블랙리스트 추가 성공")
            else:
                print(f"❌ 블랙리스트 추가 실패: {response.status_code}")
                return
            
            # 블랙리스트 추가 후 랭킹 업데이트 수신 대기
            print("\n⏳ 블랙리스트 추가 후 랭킹 업데이트 대기...")
            updated_ranking = None
            for _ in range(15):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    if data.get("type") == "RANKING_UPDATE":
                        updated_ranking = data.get("data", [])
                        break
                except asyncio.TimeoutError:
                    continue
            
            if updated_ranking:
                symbol_in_updated = any(item.get("symbol") == test_symbol for item in updated_ranking)
                print(f"\n✅ 업데이트된 랭킹 수신: {len(updated_ranking)}개 심볼")
                print(f"🔍 {test_symbol} 포함 여부: {'❌ 제거됨 (성공!)' if not symbol_in_updated else '⚠️  여전히 포함됨 (실패)'}")
                
                if not symbol_in_updated:
                    print(f"✅ 테스트 1 성공: {test_symbol}가 랭킹에서 즉시 제거되었습니다!")
                else:
                    print(f"❌ 테스트 1 실패: {test_symbol}가 여전히 랭킹에 포함되어 있습니다.")
            else:
                print("❌ 업데이트된 랭킹을 받지 못했습니다.")
            
            # 잠시 대기
            await asyncio.sleep(2)
            
            # ===== 테스트 2: 블랙리스트 해지 =====
            print_separator("테스트 2: 블랙리스트 해지 → 랭킹에 즉시 복귀")
            
            print(f"\n📤 {test_symbol}를 블랙리스트에서 해지 중...")
            response = requests.post(
                f"{BASE_URL}/api/v1/live/blacklist/remove",
                json={"symbols": [test_symbol]}
            )
            
            if response.status_code == 200:
                print(f"✅ 블랙리스트 해지 성공")
            else:
                print(f"❌ 블랙리스트 해지 실패: {response.status_code}")
                return
            
            # 블랙리스트 해지 후 랭킹 업데이트 수신 대기
            print("\n⏳ 블랙리스트 해지 후 랭킹 업데이트 대기...")
            restored_ranking = None
            for _ in range(15):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    if data.get("type") == "RANKING_UPDATE":
                        restored_ranking = data.get("data", [])
                        break
                except asyncio.TimeoutError:
                    continue
            
            if restored_ranking:
                symbol_in_restored = any(item.get("symbol") == test_symbol for item in restored_ranking)
                print(f"\n✅ 업데이트된 랭킹 수신: {len(restored_ranking)}개 심볼")
                print(f"🔍 {test_symbol} 포함 여부: {'✅ 복귀됨 (성공!)' if symbol_in_restored else '❌ 여전히 제외됨 (실패)'}")
                
                if symbol_in_restored:
                    # 복귀된 심볼의 순위 찾기
                    for i, item in enumerate(restored_ranking, 1):
                        if item.get("symbol") == test_symbol:
                            change = item.get("change_percent", 0)
                            print(f"✅ 테스트 2 성공: {test_symbol}가 랭킹 {i}위로 즉시 복귀했습니다! (상승률: {change:.2f}%)")
                            break
                else:
                    print(f"❌ 테스트 2 실패: {test_symbol}가 여전히 랭킹에서 제외되어 있습니다.")
            else:
                print("❌ 업데이트된 랭킹을 받지 못했습니다.")
            
            print_separator("테스트 완료")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_blacklist_ranking())

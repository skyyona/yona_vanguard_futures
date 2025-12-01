"""
SETTLING 기능 테스트 스크립트
"""
import asyncio
import websockets
import json
import time

async def test_settling():
    print("=" * 60)
    print("SETTLING 기능 테스트 시작")
    print("=" * 60)
    
    uri = "ws://localhost:8200/api/v1/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"\n✅ WebSocket 연결 성공: {uri}")
            
            # START 버튼 클릭 (분석 시작)
            print("\n📤 START 명령 전송 중...")
            await websocket.send(json.dumps({"action": "start"}))
            
            settling_received = False
            start_time = time.time()
            timeout = 30  # 30초 대기
            
            print(f"\n⏳ SETTLING_UPDATE 메시지 대기 중... (최대 {timeout}초)")
            print("-" * 60)
            
            while time.time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "SETTLING_UPDATE":
                        settling_received = True
                        settling_data = data.get("data", [])
                        
                        print(f"\n✅ SETTLING_UPDATE 수신 완료!")
                        print(f"총 {len(settling_data)}개 SETTLING 코인 발견")
                        print("-" * 60)
                        
                        if settling_data:
                            print("\n상위 10개 SETTLING 코인:")
                            for i, coin in enumerate(settling_data[:10], 1):
                                symbol = coin.get("symbol", "N/A")
                                change = coin.get("change_percent", 0)
                                volume = coin.get("volume", 0)
                                status = coin.get("status", "N/A")
                                print(f"{i:2d}. {symbol:15s} | 변화율: {change:7.2f}% | 거래량: {volume:>15,.0f} | 상태: {status}")
                        else:
                            print("⚠️  현재 SETTLING 상태 코인이 없습니다.")
                        
                        break
                    elif msg_type == "HEARTBEAT":
                        # HEARTBEAT는 조용히 무시
                        pass
                    else:
                        print(f"📨 기타 메시지 수신: {msg_type}")
                        
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    print(f"⏳ 대기 중... ({elapsed}초 경과)")
                    continue
            
            if not settling_received:
                print(f"\n❌ {timeout}초 내에 SETTLING_UPDATE를 받지 못했습니다.")
                print("로그를 확인하세요:")
                print("  - exchangeInfo 조회 성공 여부")
                print("  - SETTLING 상태 코인 발견 여부")
                print("  - 티커 데이터 조회 성공 여부")
            
            print("\n" + "=" * 60)
            print("테스트 완료")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_settling())

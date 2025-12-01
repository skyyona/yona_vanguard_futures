"""
NewStrategy API 엔드포인트 테스트
- /strategy/new/start, /status, /stop 검증
"""
import asyncio
import httpx
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

async def test_api_endpoints():
    """API 엔드포인트 통합 테스트"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("NewStrategy API 엔드포인트 테스트")
        print("=" * 60)
        
        # 1. 초기 상태 확인
        print("\n[1/5] 초기 상태 확인 (GET /strategy/new/status)")
        resp = await client.get(f"{BASE_URL}/strategy/new/status")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if not data.get("data", {}).get("is_running", True):
                print("✅ 초기 상태: 실행 중 아님")
        
        # 2. NewStrategy 시작
        print("\n[2/5] NewStrategy 시작 (POST /strategy/new/start)")
        start_payload = {
            "symbol": "BTCUSDT",
            "leverage": 10,
            "quantity": None  # RiskManager 자동 계산
        }
        print(f"Request: {json.dumps(start_payload, indent=2)}")
        
        resp = await client.post(
            f"{BASE_URL}/strategy/new/start",
            json=start_payload
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if data.get("status") == "success":
                print("✅ NewStrategy 시작 성공")
        else:
            print(f"❌ 시작 실패: {resp.text}")
            return
        
        # 3. 3초 대기 (전략 실행 확인)
        print("\n[3/5] 3초 대기 (전략 실행 중...)")
        await asyncio.sleep(3)
        
        # 4. 실행 중 상태 확인
        print("\n[4/5] 실행 중 상태 확인 (GET /strategy/new/status)")
        resp = await client.get(f"{BASE_URL}/strategy/new/status")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            status_data = data.get("data", {})
            if status_data.get("is_running"):
                print("✅ 전략 실행 중 확인")
                print(f"   - Symbol: {status_data.get('symbol')}")
                print(f"   - Leverage: {status_data.get('leverage')}")
                print(f"   - Orchestrator Running: {status_data.get('orchestrator_running')}")
                
                position = status_data.get("position", {})
                if position.get("quantity", 0) != 0:
                    print(f"   - Position: {position.get('direction')} {position.get('quantity')} @ {position.get('entry_price')}")
        
        # 5. NewStrategy 중지
        print("\n[5/5] NewStrategy 중지 (POST /strategy/new/stop)")
        stop_payload = {"force": True}  # 포지션 보유 시에도 강제 종료
        print(f"Request: {json.dumps(stop_payload, indent=2)}")
        
        resp = await client.post(
            f"{BASE_URL}/strategy/new/stop",
            json=stop_payload
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if data.get("status") == "success":
                print("✅ NewStrategy 중지 성공")
                if data.get("had_position"):
                    print("⚠️  포지션 보유 중이었음 (강제 종료)")
        
        # 6. 최종 상태 확인
        print("\n[6/5] 최종 상태 확인 (GET /strategy/new/status)")
        resp = await client.get(f"{BASE_URL}/strategy/new/status")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if not data.get("data", {}).get("is_running", True):
                print("✅ 최종 상태: 정상 종료됨")
        
        print("\n" + "=" * 60)
        print("테스트 완료")
        print("=" * 60)


async def test_duplicate_start():
    """중복 시작 방지 테스트"""
    print("\n" + "=" * 60)
    print("중복 시작 방지 테스트")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        start_payload = {"symbol": "ETHUSDT", "leverage": 10}
        
        # 첫 번째 시작
        print("\n[1/3] 첫 번째 시작")
        resp1 = await client.post(f"{BASE_URL}/strategy/new/start", json=start_payload)
        print(f"Status: {resp1.status_code}")
        if resp1.status_code == 200:
            print("✅ 첫 번째 시작 성공")
        
        # 두 번째 시작 (실패해야 함)
        print("\n[2/3] 두 번째 시작 (중복, 실패 예상)")
        resp2 = await client.post(f"{BASE_URL}/strategy/new/start", json=start_payload)
        print(f"Status: {resp2.status_code}")
        if resp2.status_code == 400:
            print(f"✅ 중복 시작 방지됨: {resp2.json().get('detail')}")
        else:
            print(f"❌ 중복 시작 방지 실패: {resp2.text}")
        
        # 정리
        print("\n[3/3] 정리 (중지)")
        resp3 = await client.post(f"{BASE_URL}/strategy/new/stop", json={"force": True})
        if resp3.status_code == 200:
            print("✅ 정리 완료")


if __name__ == "__main__":
    print("⚠️  Backend 서버가 http://localhost:8000 에서 실행 중이어야 합니다.")
    print("   실행 명령: python backend/app_main.py\n")
    
    try:
        # 기본 API 테스트
        asyncio.run(test_api_endpoints())
        
        # 중복 시작 방지 테스트
        # asyncio.run(test_duplicate_start())
        
    except httpx.ConnectError:
        print("\n❌ Backend 서버에 연결할 수 없습니다.")
        print("   1. backend/app_main.py 실행 확인")
        print("   2. 포트 8000이 사용 중인지 확인")
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨 (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

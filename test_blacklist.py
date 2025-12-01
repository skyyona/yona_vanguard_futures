"""
블랙리스트 기능 테스트
"""
import requests
import json

BACKEND_URL = "http://127.0.0.1:8200/api/v1"

def test_blacklist():
    """블랙리스트 기능 전체 테스트"""
    print("=" * 60)
    print("블랙리스트 기능 테스트")
    print("=" * 60)
    
    # 1. 블랙리스트 추가
    print("\n1. 블랙리스트에 심볼 추가")
    test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    response = requests.post(
        f"{BACKEND_URL}/live/blacklist/add",
        json={"symbols": test_symbols, "status": "MANUAL"}
    )
    
    if response.status_code == 200:
        print(f"   ✓ 성공: {test_symbols} 추가됨")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"블랙리스트 추가 실패: {response.status_code} - {response.text}"
    
    # 2. 블랙리스트 조회
    print("\n2. 블랙리스트 목록 조회")
    response = requests.get(f"{BACKEND_URL}/live/blacklist")
    
    if response.status_code == 200:
        result = response.json()
        data = result.get("data", [])
        print(f"   ✓ 성공: {len(data)}개 심볼 조회됨")
        for item in data:
            print(f"      - {item['symbol']}: {item['added_at_utc']} ({item['status']})")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"블랙리스트 조회 실패: {response.status_code} - {response.text}"
    
    # 3. SETTLING 상태로 심볼 추가
    print("\n3. SETTLING 상태로 심볼 추가")
    settling_symbols = ["XRPUSDT"]
    response = requests.post(
        f"{BACKEND_URL}/live/blacklist/add",
        json={"symbols": settling_symbols, "status": "SETTLING"}
    )
    
    if response.status_code == 200:
        print(f"   ✓ 성공: {settling_symbols} (SETTLING) 추가됨")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"SETTLING 추가 실패: {response.status_code} - {response.text}"
    
    # 4. 블랙리스트 재조회
    print("\n4. 블랙리스트 목록 재조회")
    response = requests.get(f"{BACKEND_URL}/live/blacklist")
    
    if response.status_code == 200:
        result = response.json()
        data = result.get("data", [])
        print(f"   ✓ 성공: {len(data)}개 심볼")
        for item in data:
            print(f"      - {item['symbol']}: {item['status']}")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"블랙리스트 재조회 실패: {response.status_code} - {response.text}"
    
    # 5. 블랙리스트에서 제거
    print("\n5. 블랙리스트에서 심볼 제거")
    remove_symbols = ["BTCUSDT", "ETHUSDT"]
    response = requests.post(
        f"{BACKEND_URL}/live/blacklist/remove",
        json={"symbols": remove_symbols}
    )
    
    if response.status_code == 200:
        print(f"   ✓ 성공: {remove_symbols} 제거됨")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"블랙리스트 제거 실패: {response.status_code} - {response.text}"
    
    # 6. 최종 블랙리스트 확인
    print("\n6. 최종 블랙리스트 확인")
    response = requests.get(f"{BACKEND_URL}/live/blacklist")
    
    if response.status_code == 200:
        result = response.json()
        data = result.get("data", [])
        print(f"   ✓ 성공: {len(data)}개 심볼 남음")
        for item in data:
            print(f"      - {item['symbol']}: {item['status']}")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"최종 블랙리스트 조회 실패: {response.status_code} - {response.text}"
    
    print("\n" + "=" * 60)
    print("블랙리스트 기능 테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_blacklist()
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

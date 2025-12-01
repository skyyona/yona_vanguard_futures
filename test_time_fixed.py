"""
시간 고정 기능 및 누적 분석 테스트
"""
import asyncio
import requests
import json
from datetime import datetime

BACKEND_URL = "http://127.0.0.1:8200/api/v1"

def test_set_fixed_time():
    """시간 고정 설정 테스트"""
    print("=" * 60)
    print("시간 고정 기능 테스트")
    print("=" * 60)
    
    # 현재 시간으로 시간 고정
    current_time = datetime.now().isoformat()
    
    print(f"\n1. 시간 고정 설정: {current_time}")
    response = requests.post(
        f"{BACKEND_URL}/set-fixed-time",
        json={"fixed_time": current_time}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ 성공: {result.get('message')}")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        return False
    
    # 잠시 대기 후 랭킹 데이터 확인
    print("\n2. 10초 대기 후 누적 데이터 확인...")
    import time
    time.sleep(10)
    
    print("   (WebSocket으로 전송된 데이터를 GUI에서 확인하세요)")
    print("   - cumulative_percent: 누적 상승률 (시간고정 이후 변동)")
    print("   - energy_type: 상승유형 (급등/지속상승/횡보/지속하락/급락)")
    
    # 시간 고정 해제
    print("\n3. 시간 고정 해제")
    response = requests.post(
        f"{BACKEND_URL}/set-fixed-time",
        json={"fixed_time": None}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ 성공: {result.get('message')}")
        print("   - cumulative_percent: +000.00 (고정 해제 상태)")
        print("   - energy_type: 데이터 분석 중")
    else:
        print(f"   ✗ 실패: {response.status_code} - {response.text}")
        return False
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        test_set_fixed_time()
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

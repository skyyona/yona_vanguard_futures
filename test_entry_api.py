"""포지션 진입 분석 API 테스트"""
import requests
import json


def test_entry_analysis_api():
    """분석 API가 제대로 작동하는지 테스트"""
    base_url = "http://127.0.0.1:8200"
    symbol = "BTCUSDT"
    
    print(f"\n🧪 포지션 진입 분석 API 테스트: {symbol}")
    print(f"URL: {base_url}/api/v1/live/analysis/entry?symbol={symbol}")
    
    try:
        response = requests.get(
            f"{base_url}/api/v1/live/analysis/entry",
            params={"symbol": symbol},
            timeout=10
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API 응답 성공!")
            print(f"\n📊 응답 데이터:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 데이터 검증
            analysis_data = data.get("data", {})
            if analysis_data:
                print(f"\n✅ 분석 데이터 검증:")
                print(f"  - symbol: {analysis_data.get('symbol')}")
                print(f"  - score: {analysis_data.get('score')}")
                print(f"  - series keys: {list(analysis_data.get('series', {}).keys())}")
                print(f"  - close prices count: {len(analysis_data.get('series', {}).get('close', []))}")
                print(f"  - trend_analysis: {analysis_data.get('trend_analysis', {}).get('overall')}")
        else:
            print(f"❌ API 오류: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ 백엔드에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")


if __name__ == "__main__":
    test_entry_analysis_api()

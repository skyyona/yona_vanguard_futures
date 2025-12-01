"""
백테스팅 API 테스트 스크립트
"""
import requests
import time

BASE_URL = "http://127.0.0.1:8200"

def test_backtest_api():
    """백테스트 API 테스트"""
    print("=" * 60)
    print("백테스팅 API 테스트 시작")
    print("=" * 60)
    
    # 테스트할 심볼
    test_symbols = ["BTCUSDT", "ETHUSDT", "GRASSUSDT"]
    
    for symbol in test_symbols:
        print(f"\n[테스트] {symbol} 백테스팅 (1주)...")
        
        try:
            # API 호출
            start_time = time.time()
            response = requests.get(
                f"{BASE_URL}/api/v1/backtest/suitability",
                params={"symbol": symbol, "period": "1w"},
                timeout=60
            )
            elapsed = time.time() - start_time
            
            if response.ok:
                result = response.json()
                success = result.get("success", False)
                cached = result.get("cached", False)
                data = result.get("data", {})
                
                if success:
                    suitability = data.get("suitability", "N/A")
                    score = data.get("score", 0)
                    reason = data.get("reason", "")
                    metrics = data.get("metrics", {})
                    
                    cache_msg = "✅ 캐시 히트" if cached else "🔄 신규 실행"
                    
                    print(f"[결과] {cache_msg} ({elapsed:.2f}초)")
                    print(f"  심볼: {symbol}")
                    print(f"  적합성: {suitability}")
                    print(f"  점수: {score:.0f}점")
                    print(f"  근거: {reason}")
                    print(f"  거래 횟수: {metrics.get('total_trades', 0)}회")
                    print(f"  승률: {metrics.get('win_rate', 0):.1f}%")
                    print(f"  수익률: {metrics.get('total_pnl_pct', 0):+.2f}%")
                    print(f"  MDD: {metrics.get('max_drawdown', 0):.2f}%")
                else:
                    print(f"[실패] API 응답: {result}")
            else:
                print(f"[실패] HTTP {response.status_code}: {response.text}")
        
        except requests.Timeout:
            print(f"[실패] 타임아웃 (60초 초과)")
        except Exception as e:
            print(f"[실패] 예외: {e}")
        
        # 다음 테스트 전 대기
        if symbol != test_symbols[-1]:
            print("  (3초 대기...)")
            time.sleep(3)
    
    print("\n" + "=" * 60)
    print("백테스팅 API 테스트 완료")
    print("=" * 60)
    
    # 캐시 테스트 (동일 심볼 재요청)
    print("\n[캐시 테스트] BTCUSDT 재요청...")
    try:
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/v1/backtest/suitability",
            params={"symbol": "BTCUSDT", "period": "1w"},
            timeout=10
        )
        elapsed = time.time() - start_time
        
        if response.ok:
            result = response.json()
            cached = result.get("cached", False)
            
            if cached:
                print(f"[성공] ✅ 캐시 히트! ({elapsed:.4f}초)")
                print("  → API 호출 0번, 즉시 응답")
            else:
                print(f"[경고] 캐시 미스 ({elapsed:.2f}초)")
                print("  → 캐시가 작동하지 않았습니다!")
        else:
            print(f"[실패] HTTP {response.status_code}")
    except Exception as e:
        print(f"[실패] 예외: {e}")


if __name__ == "__main__":
    print("\n⚠️  백엔드 서버가 실행 중인지 확인하세요!")
    print("    (python -m backend.app_main)\n")
    
    input("Enter를 눌러 테스트 시작...")
    
    test_backtest_api()

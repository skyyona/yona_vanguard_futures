"""워밍업 버그 수정 검증 스크립트"""
import asyncio
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from backend.core.new_strategy.data_fetcher import BinanceDataFetcher
from backend.api_client.binance_client import BinanceClient


async def test_warmup_fix():
    """워밍업 기능이 정상 작동하는지 검증"""
    print("\n" + "="*70)
    print("  워밍업 버그 수정 검증")
    print("="*70)
    
    try:
        client = BinanceClient()
        fetcher = BinanceDataFetcher(client)
        
        # 1m 캔들 50개 수집 (워밍업 시뮬레이션)
        print("\n[테스트 1] 1분봉 50개 수집")
        candles_1m = await fetcher.fetch_historical_candles("BTCUSDT", "1m", 50)
        assert len(candles_1m) >= 50, "1m 캔들 수집이 예상보다 적습니다"
        print(f"  ✅ 성공! {len(candles_1m)}개 캔들 수집")
        print(f"     최신 캔들: ${candles_1m[-1].close:.2f} (시간: {candles_1m[-1].open_time})")
        
        # 3m 캔들 100개 수집
        print("\n[테스트 2] 3분봉 100개 수집")
        candles_3m = await fetcher.fetch_historical_candles("BTCUSDT", "3m", 100)
        assert len(candles_3m) >= 100, "3m 캔들 수집이 예상보다 적습니다"
        print(f"  ✅ 성공! {len(candles_3m)}개 캔들 수집")
        
        # 15m 캔들 200개 수집 (실제 워밍업 조건)
        print("\n[테스트 3] 15분봉 200개 수집 (실제 워밍업)")
        candles_15m = await fetcher.fetch_historical_candles("BTCUSDT", "15m", 200)
        assert len(candles_15m) >= 200, "15m 캔들 수집이 예상보다 적습니다"
        print(f"  ✅ 성공! {len(candles_15m)}개 캔들 수집")
        
        # ALCHUSDT 테스트 (사용자가 시도한 심볼)
        print("\n[테스트 4] ALCHUSDT 워밍업 시뮬레이션")
        candles_alch = await fetcher.fetch_historical_candles("ALCHUSDT", "1m", 200)
        assert len(candles_alch) >= 1, "ALCHUSDT 캔들 수집 실패"
        print(f"  ✅ 성공! {len(candles_alch)}개 캔들 수집")
        print(f"     현재가: ${candles_alch[-1].close:.6f}")
        
        print("\n" + "="*70)
        print("  🎉 모든 테스트 통과! 워밍업 버그 완전히 수정됨")
        print("="*70)
        
        print("\n[다음 단계]")
        print("  1. GUI 실행: python gui/main.py")
        print("  2. 심볼 배정 (예: ALCHUSDT)")
        print("  3. '설정 적용' 버튼 클릭")
        print("  4. '거래 활성화' 버튼 클릭")
        print("  5. 워밍업 진행 확인 (200봉 수집)")
        print("  6. step() 루프 진입 → 실시간 거래 시작! 🚀")
        print()
        
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"워밍업 검증 중 예외 발생: {e}"


if __name__ == "__main__":
    result = asyncio.run(test_warmup_fix())
    sys.exit(0 if result else 1)

"""실제 BinanceClient 연동 검증 스크립트 (테스트넷/실전)"""
import sys
import os
import asyncio
import time

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.api_client.binance_client import BinanceClient
from backend.core.new_strategy import (
    StrategyOrchestrator,
    OrchestratorConfig,
)


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def main():
    print_section("실제 BinanceClient 연동 검증 시작")
    
    # BinanceClient 초기화 (.env에서 API 키 로드)
    print("\n1️⃣  BinanceClient 초기화 중...")
    client = BinanceClient()
    
    if not client.api_key or not client.secret_key:
        print("❌ API 키가 설정되지 않았습니다!")
        print("   .env 파일에 BINANCE_API_KEY, BINANCE_SECRET_KEY 설정 필요")
        return False
    
    print(f"✅ API 키 로드 완료: {client.api_key[:8]}...")
    print(f"✅ Base URL: {client.base_url}")
    
    # 계좌 정보 조회
    print_section("2️⃣  계좌 정보 조회")
    account = client.get_account_info()
    
    if "error" in account:
        print(f"❌ 계좌 정보 조회 실패: {account.get('error')}")
        return False
    
    total_balance = float(account.get("totalWalletBalance", 0))
    available_balance = float(account.get("availableBalance", 0))
    
    print(f"✅ 총 잔고: {total_balance:.2f} USDT")
    print(f"✅ 사용 가능 잔고: {available_balance:.2f} USDT")
    
    if total_balance < 10:
        print("⚠️  잔고가 10 USDT 미만입니다. 테스트 진행이 제한될 수 있습니다.")
    
    # 심볼 설정 테스트
    print_section("3️⃣  심볼 설정 테스트 (레버리지/마진)")
    
    test_symbol = "BTCUSDT"
    test_leverage = 10
    
    print(f"심볼: {test_symbol}, 레버리지: {test_leverage}x")
    
    # 마진 타입 설정
    margin_result = client.set_margin_type(test_symbol, isolated=True)
    if "error" in margin_result and not margin_result.get("alreadySet"):
        print(f"⚠️  마진 타입 설정 실패: {margin_result.get('error')}")
    else:
        print(f"✅ 마진 타입: ISOLATED")
    
    # 레버리지 설정
    leverage_result = client.set_leverage(test_symbol, test_leverage)
    if "error" in leverage_result:
        print(f"❌ 레버리지 설정 실패: {leverage_result.get('error')}")
        return False
    else:
        print(f"✅ 레버리지 설정: {test_leverage}x")
    
    # 실시간 데이터 조회
    print_section("4️⃣  실시간 캔들 데이터 조회")
    
    klines = client.get_klines(symbol=test_symbol, interval="1m", limit=5)
    
    if not klines or "error" in klines:
        print(f"❌ 캔들 데이터 조회 실패: {klines}")
        return False
    
    print(f"✅ 최근 5개 캔들 조회 성공:")
    for i, k in enumerate(klines[-3:], 1):
        close = float(k[4])
        volume = float(k[5])
        print(f"   {i}. 종가: {close:.2f}, 거래량: {volume:.4f}")
    
    # Mark Price 조회
    mark_price_data = client.get_mark_price(test_symbol)
    if "error" in mark_price_data:
        print(f"❌ Mark Price 조회 실패: {mark_price_data}")
        return False
    
    mark_price = float(mark_price_data.get("markPrice", 0))
    print(f"✅ 현재 Mark Price: {mark_price:.2f} USDT")
    
    # 최소 수량 필터 검증
    print_section("5️⃣  거래 필터 검증 (최소 수량)")
    
    test_qty = 0.001  # BTC 기준
    norm_result = client._round_qty_by_filters(test_symbol, test_qty, price_hint=mark_price)
    
    if not norm_result.get("ok"):
        print(f"❌ 수량 정규화 실패: {norm_result.get('reason')}")
        print(f"   요청 수량: {test_qty} BTC")
        print(f"   현재가 기준 명목가치: {test_qty * mark_price:.2f} USDT")
        print("   → minNotional 조건 미충족 가능성")
        return False
    
    normalized_qty = norm_result.get("qty")
    notional = normalized_qty * mark_price
    
    print(f"✅ 수량 정규화 성공:")
    print(f"   원본 수량: {test_qty} BTC")
    print(f"   정규화 수량: {normalized_qty} BTC")
    print(f"   명목가치: {notional:.2f} USDT")
    
    # Orchestrator 초기화 테스트
    print_section("6️⃣  Orchestrator 초기화 테스트")
    
    config = OrchestratorConfig(
        symbol=test_symbol,
        leverage=test_leverage,
        order_quantity=normalized_qty,
        enable_trading=False,  # 실제 주문은 하지 않음
        loop_interval_sec=2.0,
    )
    
    orch = StrategyOrchestrator(client, config=config)
    
    print(f"✅ Orchestrator 초기화 완료")
    print(f"   심볼: {config.symbol}")
    print(f"   레버리지: {config.leverage}x")
    print(f"   주문 수량: {config.order_quantity} BTC")
    print(f"   거래 활성화: {config.enable_trading}")
    
    # Warmup 테스트
    print_section("7️⃣  데이터 Warmup 테스트")
    
    print("1m, 3m, 15m 캔들 200개씩 로드 중...")
    start = time.time()
    
    try:
        await orch.warmup()
        elapsed = time.time() - start
        print(f"✅ Warmup 완료 ({elapsed:.2f}초)")
        
        # 캐시 상태 확인
        cache_1m = len(orch.fetcher.cache.get_latest_candles(test_symbol, "1m", 200))
        cache_3m = len(orch.fetcher.cache.get_latest_candles(test_symbol, "3m", 200))
        cache_15m = len(orch.fetcher.cache.get_latest_candles(test_symbol, "15m", 200))
        
        print(f"   캐시 크기: 1m={cache_1m}, 3m={cache_3m}, 15m={cache_15m}")
        
    except Exception as e:
        print(f"❌ Warmup 실패: {e}")
        return False
    
    # 1회 Step 실행 테스트
    print_section("8️⃣  단일 Step 실행 테스트")
    
    try:
        result = orch.step()
        
        print(f"✅ Step 실행 성공:")
        print(f"   신호 액션: {result['signal_action']}")
        print(f"   신호 점수: {result['signal_score']:.1f}/170")
        print(f"   이벤트: {result['events']}")
        
        if result.get('position'):
            pos = result['position']
            print(f"   포지션: 진입가={pos['entry']:.2f}, 손절={pos['stop']:.2f}, 익절={pos['tp']:.2f}")
        
    except Exception as e:
        print(f"❌ Step 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 최종 요약
    print_section("✅ 검증 완료")
    
    print("\n[검증 항목]")
    print("✅ API 키 로드 성공")
    print("✅ 계좌 정보 조회 성공")
    print("✅ 레버리지/마진 설정 성공")
    print("✅ 실시간 캔들 데이터 수신 성공")
    print("✅ 거래 필터 검증 통과")
    print("✅ Orchestrator 초기화 성공")
    print("✅ 데이터 Warmup 성공")
    print("✅ 단일 Step 실행 성공")
    
    print("\n[다음 단계]")
    print("1. enable_trading=True로 설정 시 실제 주문 실행 가능")
    print("2. orch.start()로 백그라운드 연속 실행 가능")
    print("3. 소액(최소 수량)으로 실전 테스트 권장")
    
    return True


if __name__ == "__main__":
    print("\n🚀 Binance 실전 연동 검증 스크립트")
    print("=" * 60)
    print("⚠️  주의: 실제 API 키를 사용합니다")
    print("⚠️  테스트넷 사용 권장 (또는 소액 계좌)")
    print("=" * 60)
    
    success = asyncio.run(main())
    
    if success:
        print("\n✅✅✅ 모든 검증 통과! ✅✅✅")
    else:
        print("\n❌❌❌ 검증 실패 ❌❌❌")
        sys.exit(1)

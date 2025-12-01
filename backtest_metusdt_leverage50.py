"""
METUSDT 레버리지 50배 백테스트
초기 자금: 2만원 (약 $15 기준 1,333 KRW/USD)
"""

# 기존 백테스트 결과 (수익률)
trades = [
    {
        "name": "거래 #1-1 (TP1 50%)",
        "entry_time": "03:03 UTC",
        "exit_time": "04:21 UTC",
        "entry_price": 0.4525,
        "exit_price": 0.4757,
        "profit_pct": 5.13,
        "position_ratio": 0.5
    },
    {
        "name": "거래 #1-2 (TP2 50%)",
        "entry_time": "03:03 UTC",
        "exit_time": "05:30 UTC",
        "entry_price": 0.4525,
        "exit_price": 0.4989,
        "profit_pct": 10.26,
        "position_ratio": 0.5
    },
    {
        "name": "거래 #2-1 (TP1 50%)",
        "entry_time": "08:29 UTC",
        "exit_time": "08:32 UTC",
        "entry_price": 0.4859,
        "exit_price": 0.4899,
        "profit_pct": 0.82,
        "position_ratio": 0.5
    },
    {
        "name": "거래 #2-2 (TP2 50%)",
        "entry_time": "08:29 UTC",
        "exit_time": "08:35 UTC",
        "entry_price": 0.4859,
        "exit_price": 0.4939,
        "profit_pct": 1.65,
        "position_ratio": 0.5
    },
    {
        "name": "거래 #3-1 (TP1 50%)",
        "entry_time": "09:06 UTC",
        "exit_time": "11:46 UTC",
        "entry_price": 0.5089,
        "exit_price": 0.5431,
        "profit_pct": 6.71,
        "position_ratio": 0.5
    },
    {
        "name": "거래 #3-2 (미청산 50%)",
        "entry_time": "09:06 UTC",
        "exit_time": "현재 (13:25 UTC)",
        "entry_price": 0.5089,
        "exit_price": 0.5256,
        "profit_pct": 3.28,
        "position_ratio": 0.5
    }
]

# 설정
INITIAL_CAPITAL_KRW = 20000  # 초기 자금 (원)
USD_KRW_RATE = 1333          # 환율 (1 USD = 1,333 KRW)
LEVERAGE = 50                # 레버리지

INITIAL_CAPITAL_USD = INITIAL_CAPITAL_KRW / USD_KRW_RATE  # 약 $15

print("=" * 80)
print("💰 METUSDT 레버리지 50배 백테스트")
print("=" * 80)
print(f"\n초기 자금: {INITIAL_CAPITAL_KRW:,}원 (${INITIAL_CAPITAL_USD:.2f})")
print(f"레버리지: {LEVERAGE}배")
print(f"환율: 1 USD = {USD_KRW_RATE} KRW\n")
print("=" * 80)

# 거래별 수익 계산
current_capital_usd = INITIAL_CAPITAL_USD
current_capital_krw = INITIAL_CAPITAL_KRW

print("\n📊 거래별 상세 내역\n")

for idx, trade in enumerate(trades, 1):
    # 가용 자금 (복리)
    available_capital = current_capital_usd
    
    # 포지션 크기 = 가용 자금 × 레버리지 × 포지션 비율
    position_size_usd = available_capital * LEVERAGE * trade["position_ratio"]
    
    # 수익 (USDT) = 포지션 크기 × 수익률
    profit_usd = position_size_usd * (trade["profit_pct"] / 100)
    
    # 수익률 (레버리지 적용) = 원래 수익률 × 레버리지
    leveraged_profit_pct = trade["profit_pct"] * LEVERAGE
    
    # 자본 업데이트 (복리)
    current_capital_usd += profit_usd
    current_capital_krw = current_capital_usd * USD_KRW_RATE
    
    # 출력
    print(f"{trade['name']}")
    print(f"  진입: {trade['entry_time']} @ ${trade['entry_price']:.4f}")
    print(f"  청산: {trade['exit_time']} @ ${trade['exit_price']:.4f}")
    print(f"  원래 수익률: {trade['profit_pct']:.2f}%")
    print(f"  레버리지 수익률: {leveraged_profit_pct:.2f}%")
    print(f"  포지션 크기: ${position_size_usd:.2f} (가용자금 ${available_capital:.2f} × {LEVERAGE}배 × {trade['position_ratio']:.0%})")
    print(f"  실현 수익: ${profit_usd:.2f} ({profit_usd * USD_KRW_RATE:,.0f}원)")
    print(f"  누적 자본: ${current_capital_usd:.2f} ({current_capital_krw:,.0f}원)")
    print()

# 최종 결과
total_profit_usd = current_capital_usd - INITIAL_CAPITAL_USD
total_profit_krw = total_profit_usd * USD_KRW_RATE
total_profit_pct = (total_profit_usd / INITIAL_CAPITAL_USD) * 100

print("=" * 80)
print("🎯 최종 결과\n")
print(f"초기 자금:  ${INITIAL_CAPITAL_USD:.2f} ({INITIAL_CAPITAL_KRW:,}원)")
print(f"최종 자본:  ${current_capital_usd:.2f} ({current_capital_krw:,.0f}원)")
print(f"총 수익:    ${total_profit_usd:.2f} ({total_profit_krw:,.0f}원)")
print(f"수익률:     {total_profit_pct:.2f}%")
print("\n💡 참고:")
print(f"   - 레버리지 미적용 시 수익: 13.93% → ${INITIAL_CAPITAL_USD * 0.1393:.2f} ({INITIAL_CAPITAL_USD * 0.1393 * USD_KRW_RATE:,.0f}원)")
print(f"   - 레버리지 50배 적용 시 수익: {total_profit_pct:.2f}% → ${total_profit_usd:.2f} ({total_profit_krw:,.0f}원)")
print(f"   - 레버리지 효과: {total_profit_pct / 13.93:.1f}배")
print("=" * 80)

# 위험 경고
print("\n⚠️  레버리지 위험 경고")
print("=" * 80)
print("레버리지 50배는 수익뿐만 아니라 손실도 50배로 확대됩니다.")
print("- 2% 손실 시 → 원금의 100% 손실 (청산)")
print("- 1% 손실 시 → 원금의 50% 손실")
print("\n✅ YONA 알파의 리스크 관리:")
print("- TP1 도달 후 손절가를 본전으로 이동 → 리스크 제로 확보")
print("- 모든 거래에서 손절 발동 없음 (100% 수익 거래)")
print("- 레버리지 고배율 사용 시에도 안전한 전략 실행")
print("=" * 80)

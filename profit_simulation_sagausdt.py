"""
SAGAUSDT 14.89% 상승 시나리오 수익 시뮬레이션
차트 데이터: 2025-11-20 17:12 ~ 19:00 (약 1시간 48분)
상승률: +14.89% (0.0891 → 0.1044)
"""
import sys
import os
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)


class TradingSimulator:
    """YONA Vanguard 엔진 리스크 관리 로직 시뮬레이터"""
    
    def __init__(self):
        # 엔진 기본 설정
        self.leverage = 50
        self.order_quantity = 100  # SAGA 기준 실용 수량 (약 $9 포지션)
        
        # 리스크 관리 설정 (RiskManagerConfig)
        self.stop_loss_pct = 0.005        # -0.5% 손절
        self.tp_primary_pct = 0.02        # +2.0% 선확정
        self.tp_extended_pct = 0.035      # +3.5% 확장 익절
        self.trailing_stop_pct = 0.006    # -0.6% 트레일링
        self.breakeven_trigger_pct = 0.01 # +1.0% 본절 이동
        
        # 거래 수수료
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
    
    def calculate_position_value(self, price: float, quantity: float) -> float:
        """포지션 가치 (USDT)"""
        return price * quantity
    
    def calculate_pnl_pct(self, entry_price: float, current_price: float) -> float:
        """손익률 (%) - LONG 기준"""
        return ((current_price / entry_price) - 1.0) * 100.0
    
    def calculate_pnl_usdt(self, entry_price: float, exit_price: float, 
                          quantity: float, leverage: int) -> dict:
        """실제 손익 (USDT) 계산 - 수수료 포함"""
        # 진입 시 필요 증거금
        position_value = entry_price * quantity
        margin = position_value / leverage
        
        # 진입 수수료 (시장가 = taker)
        entry_fee = position_value * self.taker_fee
        
        # 청산 시 포지션 가치
        exit_position_value = exit_price * quantity
        
        # 청산 수수료 (시장가 = taker, 손절/익절 모두)
        exit_fee = exit_position_value * self.taker_fee
        
        # 순손익 (레버리지 적용)
        raw_pnl = (exit_price - entry_price) * quantity
        net_pnl = raw_pnl - entry_fee - exit_fee
        
        # ROI (증거금 대비)
        roi_pct = (net_pnl / margin) * 100.0
        
        return {
            'position_value': position_value,
            'margin': margin,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'raw_pnl': raw_pnl,
            'net_pnl': net_pnl,
            'roi_pct': roi_pct,
            'pnl_pct': self.calculate_pnl_pct(entry_price, exit_price)
        }
    
    def simulate_trailing_stop(self, entry_price: float, price_path: list) -> dict:
        """트레일링 스탑 시뮬레이션"""
        # 초기 상태
        stop_loss = entry_price * (1.0 - self.stop_loss_pct)  # -0.5%
        highest_price = entry_price
        trailing_activated = False
        tp_primary_reached = False
        exit_price = None
        exit_reason = None
        
        for i, current_price in enumerate(price_path):
            # 최고가 갱신
            if current_price > highest_price:
                highest_price = current_price
            
            # 현재 손익률
            pnl_pct = self.calculate_pnl_pct(entry_price, current_price)
            
            # 1) 고정 손절 (-0.5%)
            if current_price <= stop_loss and not trailing_activated:
                exit_price = current_price
                exit_reason = "STOP_LOSS (-0.5%)"
                break
            
            # 2) 본절 이동 (+1.0% 도달)
            if pnl_pct >= self.breakeven_trigger_pct * 100.0 and not trailing_activated:
                stop_loss = max(stop_loss, entry_price)  # 본절로 상향
                trailing_activated = True
            
            # 3) +2.0% 선확정
            if pnl_pct >= self.tp_primary_pct * 100.0 and not tp_primary_reached:
                min_lock_price = entry_price * (1.0 + self.tp_primary_pct)
                stop_loss = max(stop_loss, min_lock_price)
                tp_primary_reached = True
            
            # 4) 트레일링 스탑 업데이트
            if trailing_activated:
                trail_price = highest_price * (1.0 - self.trailing_stop_pct)
                
                # +2% 확정보다 낮아지지 않도록
                if tp_primary_reached:
                    min_lock_price = entry_price * (1.0 + self.tp_primary_pct)
                    trail_price = max(trail_price, min_lock_price)
                
                stop_loss = max(stop_loss, trail_price)
                
                # 트레일링 스탑 체결
                if current_price <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = f"TRAILING_STOP (최고가: {highest_price:.4f}, -0.6%)"
                    break
            
            # 5) 확장 익절 (+3.5%)
            tp_extended_price = entry_price * (1.0 + self.tp_extended_pct)
            if current_price >= tp_extended_price:
                exit_price = current_price
                exit_reason = "EXTENDED_TP (+3.5%)"
                break
        
        # 경로 끝까지 보유한 경우
        if exit_price is None:
            exit_price = price_path[-1]
            exit_reason = "HOLDING (시뮬레이션 종료)"
        
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'highest_price': highest_price,
            'trailing_activated': trailing_activated,
            'tp_primary_reached': tp_primary_reached,
            'final_stop_loss': stop_loss
        }


def run_sagausdt_simulation():
    """SAGAUSDT 14.89% 상승 시나리오 분석"""
    print("\n" + "="*70)
    print("  SAGAUSDT 상승률 14.89% 시나리오 - 수익 시뮬레이션")
    print("="*70)
    
    simulator = TradingSimulator()
    
    # === 차트 데이터 분석 ===
    print("\n[1] 차트 데이터 정보")
    print("-" * 70)
    
    # 실제 가격 경로 (이미지 기반 추정)
    # 17:12 시작 → 18:00 급등 → 18:15 고점 → 하락 시작
    entry_price = 0.0891  # 급등 직전
    peak_price = 0.1106   # 고점 (이미지 좌측 상단 툴팁)
    current_price = 0.1044 # 19:00 현재가
    
    actual_rise = ((peak_price / entry_price) - 1.0) * 100.0
    current_rise = ((current_price / entry_price) - 1.0) * 100.0
    
    print(f"  진입가 (추정): ${entry_price:.4f}")
    print(f"  최고가: ${peak_price:.4f} (+{actual_rise:.2f}%)")
    print(f"  현재가 (19:00): ${current_price:.4f} (+{current_rise:.2f}%)")
    print(f"  고점 대비 하락: {((current_price/peak_price - 1.0)*100.0):.2f}%")
    
    # === 가격 경로 시뮬레이션 ===
    print("\n[2] 가격 경로 재구성 (1분봉 추정)")
    print("-" * 70)
    
    # 실제 패턴: 완만 → 급등(15분) → 고점(3분) → 급락(10분) → 횡보
    price_path = []
    
    # 17:12-17:45: 완만 상승 (0.0891 → 0.095)
    for i in range(33):
        price_path.append(0.0891 + (0.004 * i / 33))
    
    # 17:45-18:00: 급등 1단계 (0.095 → 0.103)
    for i in range(15):
        price_path.append(0.095 + (0.008 * i / 15))
    
    # 18:00-18:03: 폭등 (0.103 → 0.1106 고점)
    for i in range(3):
        price_path.append(0.103 + (0.0076 * i / 3))
    
    # 18:03-18:13: 급락 (0.1106 → 0.098)
    for i in range(10):
        price_path.append(0.1106 - (0.0126 * i / 10))
    
    # 18:13-19:00: 반등 및 횡보 (0.098 → 0.1044)
    for i in range(47):
        price_path.append(0.098 + (0.0064 * i / 47))
    
    print(f"  총 캔들 수: {len(price_path)}개 (약 {len(price_path)}분)")
    print(f"  경로 최저가: ${min(price_path):.4f}")
    print(f"  경로 최고가: ${max(price_path):.4f}")
    
    # === 엔진 로직 시뮬레이션 ===
    print("\n[3] YONA Vanguard 엔진 트레일링 스탑 시뮬레이션")
    print("-" * 70)
    
    result = simulator.simulate_trailing_stop(entry_price, price_path)
    
    print(f"  진입가: ${result['entry_price']:.4f}")
    print(f"  최고가 도달: ${result['highest_price']:.4f} "
          f"(+{simulator.calculate_pnl_pct(entry_price, result['highest_price']):.2f}%)")
    print(f"  본절 이동: {'✅ 활성화 (+1.0% 도달)' if result['trailing_activated'] else '❌'}")
    print(f"  선확정 (+2%): {'✅ 도달' if result['tp_primary_reached'] else '❌'}")
    print(f"  최종 스탑로스: ${result['final_stop_loss']:.4f}")
    print(f"\n  🔔 청산가: ${result['exit_price']:.4f}")
    print(f"  🔔 청산 사유: {result['exit_reason']}")
    
    # === 손익 계산 ===
    print("\n[4] 실제 손익 계산 (레버리지 50배)")
    print("-" * 70)
    
    pnl = simulator.calculate_pnl_usdt(
        entry_price=result['entry_price'],
        exit_price=result['exit_price'],
        quantity=simulator.order_quantity,
        leverage=simulator.leverage
    )
    
    print(f"  주문 수량: {simulator.order_quantity} SAGA")
    print(f"  포지션 가치: ${pnl['position_value']:.2f} USDT")
    print(f"  필요 증거금: ${pnl['margin']:.4f} USDT (레버리지 {simulator.leverage}배)")
    print(f"\n  진입 수수료: ${pnl['entry_fee']:.4f} USDT (0.05%)")
    print(f"  청산 수수료: ${pnl['exit_fee']:.4f} USDT (0.05%)")
    print(f"\n  가격 손익: ${pnl['raw_pnl']:.4f} USDT ({pnl['pnl_pct']:.2f}%)")
    print(f"  순손익: ${pnl['net_pnl']:.4f} USDT")
    print(f"\n  ⭐ ROI (증거금 대비): {pnl['roi_pct']:.2f}%")
    
    # === 시나리오 비교 ===
    print("\n[5] 시나리오 비교 분석")
    print("-" * 70)
    
    # A) 최악: 초기 손절 (-0.5%)
    worst = simulator.calculate_pnl_usdt(
        entry_price, entry_price * (1.0 - 0.005), simulator.order_quantity, simulator.leverage
    )
    
    # B) 보통: +2% 선확정에서 즉시 청산
    normal = simulator.calculate_pnl_usdt(
        entry_price, entry_price * (1.0 + 0.02), simulator.order_quantity, simulator.leverage
    )
    
    # C) 우수: +3.5% 확장 익절
    best = simulator.calculate_pnl_usdt(
        entry_price, entry_price * (1.0 + 0.035), simulator.order_quantity, simulator.leverage
    )
    
    # D) 고점 청산 (비현실적 - 참고용)
    peak = simulator.calculate_pnl_usdt(
        entry_price, peak_price, simulator.order_quantity, simulator.leverage
    )
    
    print(f"  A) 손절 (-0.5%): ${worst['net_pnl']:.4f} USDT (ROI: {worst['roi_pct']:.2f}%)")
    print(f"  B) 선확정 (+2.0%): ${normal['net_pnl']:.4f} USDT (ROI: {normal['roi_pct']:.2f}%)")
    print(f"  C) 확장익절 (+3.5%): ${best['net_pnl']:.4f} USDT (ROI: {best['roi_pct']:.2f}%)")
    print(f"  D) 고점청산 (참고): ${peak['net_pnl']:.4f} USDT (ROI: {peak['roi_pct']:.2f}%)")
    print(f"\n  ✅ 실제 엔진 결과: ${pnl['net_pnl']:.4f} USDT (ROI: {pnl['roi_pct']:.2f}%)")
    
    # === 결론 ===
    print("\n[6] 결론 및 평가")
    print("-" * 70)
    
    efficiency = (pnl['net_pnl'] / peak['net_pnl']) * 100.0
    vs_hold = pnl['pnl_pct'] - current_rise
    
    print(f"  📊 상승 포착률: {efficiency:.1f}% (고점 대비)")
    print(f"  📊 홀드 대비: {vs_hold:+.2f}%p "
          f"({'우수' if vs_hold > 0 else '보유가 유리'})")
    
    print(f"\n  💡 트레일링 스탑 효과:")
    print(f"     - 최고가 {result['highest_price']:.4f} 도달 후")
    print(f"     - -0.6% 하락 시 자동 청산으로 이익 보호")
    print(f"     - +2% 선확정으로 최소 수익 보장")
    
    print(f"\n  🎯 엔진 강점:")
    print(f"     - 급등 시 본절 이동 (+1%) → 손실 방지")
    print(f"     - 선확정 (+2%) → 최소 수익 확보")
    print(f"     - 트레일링 (-0.6%) → 하락 전 청산")
    
    print(f"\n  ⚠️  한계:")
    print(f"     - 고점 청산 불가 (인간도 어려움)")
    print(f"     - 급락 시 슬리피지 가능 (시장가 주문)")
    print(f"     - 수수료 부담 (진입+청산 0.1%)")
    
    print("\n" + "="*70)
    print(f"  ⭐ 최종 결과: 증거금 ${pnl['margin']:.4f} 투입")
    print(f"  ⭐ 순수익: ${pnl['net_pnl']:.4f} USDT")
    print(f"  ⭐ 수익률: {pnl['roi_pct']:.2f}% (레버리지 50배 적용)")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        run_sagausdt_simulation()
    except Exception as e:
        print(f"\n❌ 시뮬레이션 오류: {e}")
        import traceback
        traceback.print_exc()

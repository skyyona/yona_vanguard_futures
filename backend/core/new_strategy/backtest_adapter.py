"""
BacktestAdapter: NewStrategy 백테스트 어댑터
- 과거 데이터 로드 (Binance Klines)
- Orchestrator 시뮬레이션 모드
- 성능 메트릭 계산 (PNL, MDD, 승률, Sharpe)
"""
import logging
from backend.core.new_strategy.data_structures import Candle
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """과거 데이터 로더"""
    
    def __init__(self, binance_client):
        self.client = binance_client
    
    def load_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int
    ) -> List[List]:
        """
        과거 캔들 데이터 로드
        
        Args:
            symbol: 코인 심볼
            interval: 타임프레임 ("1m", "3m", "15m")
            start_ts: 시작 타임스탬프 (ms)
            end_ts: 종료 타임스탬프 (ms)
        
        Returns:
            캔들 데이터 리스트
        """
        all_klines = []
        current_ts = start_ts
        limit = 1000  # 한 번에 최대 1000개
        
        while current_ts < end_ts:
            try:
                # BinanceClient의 get_klines 메서드 사용
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    start_time=current_ts,
                    end_time=end_ts
                )
                
                if isinstance(klines, list) and len(klines) > 0:
                    all_klines.extend(klines)
                    
                    # 다음 배치 시작 시간 설정
                    last_ts = int(klines[-1][0])  # 마지막 캔들의 open_time
                    if last_ts >= current_ts:
                        current_ts = last_ts + 1
                    else:
                        break
                else:
                    break
            
            except Exception as e:
                logger.error(f"[BacktestDataLoader] 데이터 로드 오류: {symbol} {interval} - {e}")
                break
        
        logger.info(f"[BacktestDataLoader] 로드 완료: {symbol} {interval} - {len(all_klines)}개 캔들")
        return all_klines
    
    def klines_to_dataframe(self, klines: List[List]) -> pd.DataFrame:
        """
        캔들 데이터를 DataFrame으로 변환
        
        Args:
            klines: 캔들 데이터 리스트
        
        Returns:
            DataFrame
        """
        if not klines:
            return pd.DataFrame()
        
        # Binance klines 형식: [open_time, open, high, low, close, volume, close_time, quote_volume, trades, ...]
        data = []
        for k in klines:
            open_time = int(k[0])
            timestamp = datetime.fromtimestamp(open_time / 1000)
            
            data.append({
                "timestamp": timestamp,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "quote_volume": float(k[7]) if len(k) > 7 else float(k[5]) * float(k[4]),
                "trades": int(k[8]) if len(k) > 8 else 0
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        return df


class BacktestConfig:
    """백테스트 설정"""
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        start_date: str = "2024-01-01",
        end_date: str = "2024-01-31",
        initial_balance: float = 10000.0,
        leverage: int = 10,
        commission_rate: float = 0.0004,  # 0.04% (Maker/Taker 평균)
        slippage_rate: float = 0.0001,    # 0.01% (시뮬레이션 슬리피지)
    ):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate


class BacktestExecutor:
    """백테스트 실행 엔진"""

    INTERVAL_MS = {
        "1m": 60 * 1000,
        "3m": 3 * 60 * 1000,
        "15m": 15 * 60 * 1000,
    }

    def __init__(
        self,
        orchestrator,
        config: BacktestConfig,
        klines_1m: pd.DataFrame,
        klines_3m: pd.DataFrame,
        klines_15m: pd.DataFrame,
    ):
        self.orchestrator = orchestrator
        self.config = config
        self.klines_1m = klines_1m
        self.klines_3m = klines_3m
        self.klines_15m = klines_15m

        # 백테스트 상태
        self.balance = config.initial_balance
        self.position = None  # SimulatedPosition
        self.trades = []      # List[Dict[str, Any]]
        self.equity_curve = [] # List[Dict[str, Any]]

        # 데이터 인덱스
        self.current_1m_idx = 0
        self.current_3m_idx = 0
        self.current_15m_idx = 0

    def _dataframe_to_candles(self, df, symbol, interval):
        """DataFrame을 Candle 리스트로 변환 (모든 필드 일관성 보장)"""
        from backend.core.new_strategy.data_structures import Candle
        interval_ms = self.INTERVAL_MS[interval]
        candles = []
        for _, row in df.iterrows():
            # timestamp 필드가 datetime이면 ms로 변환, int면 그대로 사용
            if hasattr(row["timestamp"], "timestamp"):
                open_time = int(row["timestamp"].timestamp() * 1000)
            else:
                open_time = int(row["timestamp"])
            close_time = open_time + interval_ms - 1
            candle = Candle(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=close_time,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                quote_volume=float(row["quote_volume"]) if "quote_volume" in row and row["quote_volume"] is not None else 0.0,
                trades_count=int(row["trades"]) if "trades" in row and row["trades"] is not None else 0
            )
            candles.append(candle)
        return candles

    def run(self) -> Dict[str, Any]:
        """
        백테스트 실행
        Returns:
            {
                "total_pnl": float,
                "total_trades": int,
                "win_rate": float,
                "max_drawdown": float,
                "sharpe_ratio": float,
                "trades": List[Dict],
                "equity_curve": List[Dict]
            }
        """
        logger.info(f"Starting backtest for {self.config.symbol} "
                   f"from {self.config.start_date} to {self.config.end_date}")

        # 1분봉 기준으로 순회
        total_candles = len(self.klines_1m)

        for idx in range(total_candles):
            current_candle = self.klines_1m.iloc[idx]
            current_time = current_candle["timestamp"]
            current_price = current_candle["close"]

            # 3분봉/15분봉 인덱스 업데이트
            self._update_timeframe_indices(current_time)

            # Orchestrator에 현재 데이터 주입 (실제 구현 시 필요)
            # orchestrator.data_fetcher.cache를 임시로 업데이트
            self._inject_data_to_orchestrator(idx)

            # Orchestrator step 실행
            try:
                result = self.orchestrator.step()

                # 진입 시그널 처리
                if result.get("entry_triggered") and self.position is None:
                    self._handle_entry(result, current_price, current_time)

                # 청산 시그널 처리
                if result.get("exit_triggered") and self.position is not None:
                    self._handle_exit(result, current_price, current_time)

            except Exception as e:
                logger.error(f"Backtest step failed at {current_time}: {e}")
                continue

            # 에퀴티 커브 기록 (매 100번째 캔들)
            if idx % 100 == 0:
                current_equity = self.balance
                if self.position:
                    current_equity += self.position.calculate_pnl(current_price)

                self.equity_curve.append({
                    "timestamp": current_time,
                    "equity": current_equity,
                    "balance": self.balance,
                    "position_pnl": self.position.calculate_pnl(current_price) if self.position else 0
                })

            # 진행률 표시
            if idx % 1000 == 0:
                progress = (idx / total_candles) * 100
                logger.info(f"Backtest progress: {progress:.1f}% ({idx}/{total_candles})")

        # 미청산 포지션 강제 청산
        if self.position:
            final_price = self.klines_1m.iloc[-1]["close"]
            final_time = self.klines_1m.iloc[-1]["timestamp"]
            self._handle_exit({"exit_reason": "BACKTEST_END"}, final_price, final_time)

        # 성능 메트릭 계산
        metrics = self._calculate_metrics()

        logger.info(f"Backtest completed: {len(self.trades)} trades, "
                   f"Total PNL: {metrics['total_pnl']:.2f} USDT "
                   f"({metrics['total_pnl_pct']:.2f}%)")

        return metrics

    def _update_timeframe_indices(self, current_time: datetime):
        # 현재 시간에 맞춰 3m/15m 인덱스 업데이트
        # 3분봉 인덱스
        while (self.current_3m_idx < len(self.klines_3m) - 1 and
               self.klines_3m.iloc[self.current_3m_idx]["timestamp"] <= current_time):
            self.current_3m_idx += 1

        # 15분봉 인덱스
        while (self.current_15m_idx < len(self.klines_15m) - 1 and
               self.klines_15m.iloc[self.current_15m_idx]["timestamp"] <= current_time):
            self.current_15m_idx += 1

    def _inject_data_to_orchestrator(self, idx: int):
        # Orchestrator의 DataFetcher 캐시에 백테스트 데이터 주입
        symbol = self.config.symbol
        # 캐시 초기화 (기존 데이터 제거)
        self.orchestrator.fetcher.cache.clear(symbol)

        # 1분봉: 현재 인덱스까지의 최신 200개
        start_1m = max(0, idx + 1 - 200)
        df_1m_slice = self.klines_1m.iloc[start_1m:idx+1]
        candles_1m = self._dataframe_to_candles(df_1m_slice, symbol, "1m")

        # 3분봉: 현재 3m 인덱스까지의 최신 200개
        start_3m = max(0, self.current_3m_idx + 1 - 200)
        df_3m_slice = self.klines_3m.iloc[start_3m:self.current_3m_idx+1]
        candles_3m = self._dataframe_to_candles(df_3m_slice, symbol, "3m")

        # 15분봉: 현재 15m 인덱스까지의 최신 200개
        start_15m = max(0, self.current_15m_idx + 1 - 200)
        df_15m_slice = self.klines_15m.iloc[start_15m:self.current_15m_idx+1]
        candles_15m = self._dataframe_to_candles(df_15m_slice, symbol, "15m")

        # 캐시에 주입
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_1m)
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_3m)
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_15m)

        logger.debug(
            f"[Backtest] 데이터 주입: 1m={len(candles_1m)}, "
            f"3m={len(candles_3m)}, 15m={len(candles_15m)} @ idx={idx}"
        )

    def _handle_entry(self, result: Dict, price: float, timestamp: datetime):
        # 진입 시그널 처리
        direction = result.get("entry_signal", {}).get("direction", "LONG")
        quantity = result.get("position_size", 0.001)  # RiskManager 계산 결과

        self.position = SimulatedPosition(
            direction=direction,
            quantity=quantity,
            entry_price=price,
            commission_rate=self.config.commission_rate,
            slippage_rate=self.config.slippage_rate,
        )

        logger.info(f"[ENTRY] {direction} {quantity} @ {price} at {timestamp}")

    def _handle_exit(self, result: Dict, price: float, timestamp: datetime):
        """청산 시그널 처리"""
        if not self.position:
            return

        pnl = self.position.calculate_pnl(price)
        self.balance += pnl

        exit_reason = result.get("exit_reason", "SIGNAL")

        trade_record = {
            "entry_time": self.position.entry_time,
            "exit_time": timestamp,
            "direction": self.position.direction,
            "quantity": self.position.quantity,
            "entry_price": self.position.effective_entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_pct": (pnl / (self.position.effective_entry_price * self.position.quantity)) * 100,
            "exit_reason": exit_reason,
        }

        self.trades.append(trade_record)

        logger.info(f"[EXIT] {exit_reason} @ {price} | PNL: {pnl:.2f} USDT ({trade_record['pnl_pct']:.2f}%)")

        self.position = None

    def _calculate_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 계산"""
        if not self.trades:
            return {
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "total_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "trades": [],
                "equity_curve": self.equity_curve,
            }

        total_pnl = sum(t["pnl"] for t in self.trades)
        total_pnl_pct = (total_pnl / self.config.initial_balance) * 100

        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]

        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

        # 최대 낙폭 (MDD) 계산
        equity_values = [eq["equity"] for eq in self.equity_curve]
        if equity_values:
            peak = equity_values[0]
            max_dd = 0
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            max_drawdown = max_dd * 100
        else:
            max_drawdown = 0

        # Sharpe Ratio 계산 (간단 버전)
        if len(self.trades) > 1:
            pnl_series = [t["pnl"] for t in self.trades]
            avg_pnl = np.mean(pnl_series)
            std_pnl = np.std(pnl_series)
            sharpe_ratio = (avg_pnl / std_pnl) * np.sqrt(len(self.trades)) if std_pnl > 0 else 0
        else:
            sharpe_ratio = 0

        return {
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses else float('inf'),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }
class SimulatedPosition:
    """시뮬레이션 포지션 (실제 주문 없음)"""

    def __init__(
        self,
        direction: str,
        quantity: float,
        entry_price: float,
        commission_rate: float = 0.0004,
        slippage_rate: float = 0.0001,
    ):
        self.direction = direction  # "LONG" or "SHORT"
        self.quantity = quantity
        self.entry_price = entry_price
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

        # 진입 시 슬리피지 & 수수료 적용
        if direction == "LONG":
            self.effective_entry_price = entry_price * (1 + slippage_rate)
        else:
            self.effective_entry_price = entry_price * (1 - slippage_rate)

        self.entry_commission = abs(quantity * self.effective_entry_price * commission_rate)
        self.entry_time = datetime.now()

    def calculate_pnl(self, current_price: float) -> float:
        # 현재 가격 기준 미실현 손익 계산 (수수료 포함)
        if self.direction == "LONG":
            # 청산 시 슬리피지 & 수수료 적용
            exit_price = current_price * (1 - self.slippage_rate)
            pnl = (exit_price - self.effective_entry_price) * self.quantity
        else:
            exit_price = current_price * (1 + self.slippage_rate)
            pnl = (self.effective_entry_price - exit_price) * self.quantity
        exit_commission = abs(self.quantity * exit_price * self.commission_rate)
        net_pnl = pnl - self.entry_commission - exit_commission
        return net_pnl


class BacktestExecutor:
    # 타임프레임별 밀리초 간격 상수
    INTERVAL_MS = {
        "1m": 60 * 1000,
        "3m": 3 * 60 * 1000,
        "15m": 15 * 60 * 1000,
    }

    def _dataframe_to_candles(self, df, symbol, interval):
        """DataFrame을 Candle 리스트로 변환"""
        from backend.core.new_strategy.data_structures import Candle
        interval_ms = self.INTERVAL_MS[interval]
        candles = []
        for _, row in df.iterrows():
            open_time = int(row["timestamp"].timestamp() * 1000)
            close_time = open_time + interval_ms - 1
            candle = Candle(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=close_time,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                quote_volume=float(row["quote_volume"]) if "quote_volume" in row else 0,
                trades_count=int(row["trades"]) if "trades" in row else 0
            )
            candles.append(candle)
        return candles

    def __init__(
        self,
        orchestrator,
        config: BacktestConfig,
        klines_1m: pd.DataFrame,
        klines_3m: pd.DataFrame,
        klines_15m: pd.DataFrame,
    ):
        self.orchestrator = orchestrator
        self.config = config
        self.klines_1m = klines_1m
        self.klines_3m = klines_3m
        self.klines_15m = klines_15m

        # 백테스트 상태
        self.balance = config.initial_balance
        self.position = None  # SimulatedPosition
        self.trades = []      # List[Dict[str, Any]]
        self.equity_curve = [] # List[Dict[str, Any]]

        # 데이터 인덱스
        self.current_1m_idx = 0
        self.current_3m_idx = 0
        self.current_15m_idx = 0

    def run(self) -> Dict[str, Any]:
        """
        백테스트 실행
        Returns:
            {
                "total_pnl": float,
                "total_trades": int,
                "win_rate": float,
                "max_drawdown": float,
                "sharpe_ratio": float,
                "trades": List[Dict],
                "equity_curve": List[Dict]
            }
        """
        logger.info(f"Starting backtest for {self.config.symbol} "
                   f"from {self.config.start_date} to {self.config.end_date}")

        # 1분봉 기준으로 순회
        total_candles = len(self.klines_1m)

        for idx in range(total_candles):
            current_candle = self.klines_1m.iloc[idx]
            current_time = current_candle["timestamp"]
            current_price = current_candle["close"]

            # 3분봉/15분봉 인덱스 업데이트
            self._update_timeframe_indices(current_time)

            # Orchestrator에 현재 데이터 주입 (실제 구현 시 필요)
            # orchestrator.data_fetcher.cache를 임시로 업데이트
            self._inject_data_to_orchestrator(idx)

            # Orchestrator step 실행
            try:
                result = self.orchestrator.step()

                # 진입 시그널 처리
                if result.get("entry_triggered") and self.position is None:
                    self._handle_entry(result, current_price, current_time)

                # 청산 시그널 처리
                if result.get("exit_triggered") and self.position is not None:
                    self._handle_exit(result, current_price, current_time)

            except Exception as e:
                logger.error(f"Backtest step failed at {current_time}: {e}")
                continue

            # 에퀴티 커브 기록 (매 100번째 캔들)
            if idx % 100 == 0:
                current_equity = self.balance
                if self.position:
                    current_equity += self.position.calculate_pnl(current_price)

                self.equity_curve.append({
                    "timestamp": current_time,
                    "equity": current_equity,
                    "balance": self.balance,
                    "position_pnl": self.position.calculate_pnl(current_price) if self.position else 0
                })

            # 진행률 표시
            if idx % 1000 == 0:
                progress = (idx / total_candles) * 100
                logger.info(f"Backtest progress: {progress:.1f}% ({idx}/{total_candles})")

        # 미청산 포지션 강제 청산
        if self.position:
            final_price = self.klines_1m.iloc[-1]["close"]
            final_time = self.klines_1m.iloc[-1]["timestamp"]
            self._handle_exit({"exit_reason": "BACKTEST_END"}, final_price, final_time)

        # 성능 메트릭 계산
        metrics = self._calculate_metrics()

        logger.info(f"Backtest completed: {len(self.trades)} trades, "
                   f"Total PNL: {metrics['total_pnl']:.2f} USDT "
                   f"({metrics['total_pnl_pct']:.2f}%)")

        return metrics

    def _update_timeframe_indices(self, current_time: datetime):
        # 현재 시간에 맞춰 3m/15m 인덱스 업데이트
        # 3분봉 인덱스
        while (self.current_3m_idx < len(self.klines_3m) - 1 and
               self.klines_3m.iloc[self.current_3m_idx]["timestamp"] <= current_time):
            self.current_3m_idx += 1

        # 15분봉 인덱스
        while (self.current_15m_idx < len(self.klines_15m) - 1 and
               self.klines_15m.iloc[self.current_15m_idx]["timestamp"] <= current_time):
            self.current_15m_idx += 1

    def _inject_data_to_orchestrator(self, idx: int):
        # Orchestrator의 DataFetcher 캐시에 백테스트 데이터 주입
        symbol = self.config.symbol
        # 캐시 초기화 (기존 데이터 제거)
        self.orchestrator.fetcher.cache.clear(symbol)

        # 1분봉: 현재 인덱스까지의 최신 200개
        start_1m = max(0, idx + 1 - 200)
        df_1m_slice = self.klines_1m.iloc[start_1m:idx+1]
        candles_1m = self._dataframe_to_candles(df_1m_slice, symbol, "1m")

        # 3분봉: 현재 3m 인덱스까지의 최신 200개
        start_3m = max(0, self.current_3m_idx + 1 - 200)
        df_3m_slice = self.klines_3m.iloc[start_3m:self.current_3m_idx+1]
        candles_3m = self._dataframe_to_candles(df_3m_slice, symbol, "3m")

        # 15분봉: 현재 15m 인덱스까지의 최신 200개
        start_15m = max(0, self.current_15m_idx + 1 - 200)
        df_15m_slice = self.klines_15m.iloc[start_15m:self.current_15m_idx+1]
        candles_15m = self._dataframe_to_candles(df_15m_slice, symbol, "15m")

        # 캐시에 주입
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_1m)
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_3m)
        self.orchestrator.fetcher.cache.add_candles_bulk(candles_15m)

        logger.debug(
            f"[Backtest] 데이터 주입: 1m={len(candles_1m)}, "
            f"3m={len(candles_3m)}, 15m={len(candles_15m)} @ idx={idx}"
        )

    def _handle_entry(self, result: Dict, price: float, timestamp: datetime):
        # 진입 시그널 처리
        direction = result.get("entry_signal", {}).get("direction", "LONG")
        quantity = result.get("position_size", 0.001)  # RiskManager 계산 결과

        self.position = SimulatedPosition(
            direction=direction,
            quantity=quantity,
            entry_price=price,
            commission_rate=self.config.commission_rate,
            slippage_rate=self.config.slippage_rate,
        )

        logger.info(f"[ENTRY] {direction} {quantity} @ {price} at {timestamp}")

    def _handle_exit(self, result: Dict, price: float, timestamp: datetime):
        """청산 시그널 처리"""
        if not self.position:
            return

        pnl = self.position.calculate_pnl(price)
        self.balance += pnl

        exit_reason = result.get("exit_reason", "SIGNAL")

        trade_record = {
            "entry_time": self.position.entry_time,
            "exit_time": timestamp,
            "direction": self.position.direction,
            "quantity": self.position.quantity,
            "entry_price": self.position.effective_entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_pct": (pnl / (self.position.effective_entry_price * self.position.quantity)) * 100,
            "exit_reason": exit_reason,
        }

        self.trades.append(trade_record)

        logger.info(f"[EXIT] {exit_reason} @ {price} | PNL: {pnl:.2f} USDT ({trade_record['pnl_pct']:.2f}%)")

        self.position = None

    def _calculate_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 계산"""
        if not self.trades:
            return {
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "total_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "trades": [],
                "equity_curve": self.equity_curve,
            }

        total_pnl = sum(t["pnl"] for t in self.trades)
        total_pnl_pct = (total_pnl / self.config.initial_balance) * 100

        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]

        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

        # 최대 낙폭 (MDD) 계산
        equity_values = [eq["equity"] for eq in self.equity_curve]
        if equity_values:
            peak = equity_values[0]
            max_dd = 0
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            max_drawdown = max_dd * 100
        else:
            max_drawdown = 0

        # Sharpe Ratio 계산 (간단 버전)
        if len(self.trades) > 1:
            pnl_series = [t["pnl"] for t in self.trades]
            avg_pnl = np.mean(pnl_series)
            std_pnl = np.std(pnl_series)
            sharpe_ratio = (avg_pnl / std_pnl) * np.sqrt(len(self.trades)) if std_pnl > 0 else 0
        else:
            sharpe_ratio = 0

        return {
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses else float('inf'),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }


class BacktestAdapter:
    """백테스트 어댑터 (통합 인터페이스)"""

    def __init__(self, binance_client):
        self.client = binance_client
        self.data_loader = BacktestDataLoader(binance_client)

    def run_backtest(
        self,
        orchestrator,
        config: BacktestConfig
    ) -> Dict[str, Any]:
        # 백테스트 실행
        # Args:
        #   orchestrator: StrategyOrchestrator 인스턴스
        #   config: BacktestConfig
        # Returns:
        #   성능 메트릭 딕셔너리
        # 1. 과거 데이터 로드
        start_ts = int(datetime.strptime(config.start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(config.end_date, "%Y-%m-%d").timestamp() * 1000)

        logger.info(f"Loading historical data for {config.symbol}...")

        klines_1m_raw = self.data_loader.load_historical_klines(
            config.symbol, "1m", start_ts, end_ts
        )
        klines_3m_raw = self.data_loader.load_historical_klines(
            config.symbol, "3m", start_ts, end_ts
        )
        klines_15m_raw = self.data_loader.load_historical_klines(
            config.symbol, "15m", start_ts, end_ts
        )

        klines_1m = self.data_loader.klines_to_dataframe(klines_1m_raw)
        klines_3m = self.data_loader.klines_to_dataframe(klines_3m_raw)
        klines_15m = self.data_loader.klines_to_dataframe(klines_15m_raw)

        logger.info(f"Loaded {len(klines_1m)} 1m, {len(klines_3m)} 3m, {len(klines_15m)} 15m candles")

        if klines_1m.empty:
            raise ValueError(f"No data loaded for {config.symbol} in the given date range")

        # 2. 백테스트 실행
        executor = BacktestExecutor(
            orchestrator=orchestrator,
            config=config,
            klines_1m=klines_1m,
            klines_3m=klines_3m,
            klines_15m=klines_15m,
        )

        results = executor.run()

        return results

"""엔진 매니저 - 3개 자동매매 엔진 통합 관리"""
import asyncio
from typing import Dict, Any, Optional, List
import threading
import time
import os
import aiosqlite
from datetime import datetime
import json

import requests
from backend.utils.config_loader import ENABLE_ENGINE_EXECUTOR, ENGINE_EXECUTOR_URL

from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy


class EngineManager:
    """
    3개 자동매매 엔진(Alpha, Beta, Gamma)을 통합 관리하는 매니저
    
    역할:
    - 각 엔진의 시작/정지 제어
    - 엔진 상태 모니터링
    - WebSocket을 통한 GUI 업데이트
    - 로그 메시지 전송
    """
    
    def __init__(self, realized_pnl_callback=None, db_path: Optional[str] = None):
        """
        엔진 매니저 초기화
        
        Args:
            realized_pnl_callback: 실현 손익 전달 콜백 (engine_name, amount)
            db_path: 데이터베이스 파일 경로 (거래 기록 저장용)
        """
        self.engines: Dict[str, Any] = {}
        self._message_callbacks = []
        self._realized_pnl_callback = realized_pnl_callback
        self._lock = threading.Lock()
        self._monitor_thread = None
        self._is_monitoring = False
        
        # 각 엔진의 이전 포지션 상태 추적 (거래 종료 감지용)
        self._previous_position_states: Dict[str, bool] = {}
        
        # 데이터베이스 경로 (거래 기록 저장용)
        if db_path is None:
            # 기본 경로 설정
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(current_dir, "yona_vanguard.db")
        self._db_path = db_path
        
        # ✅ 공유 BinanceClient 생성 (핵심: 의존성 주입 패턴)
        from backend.api_client.binance_client import BinanceClient
        self._shared_binance_client = BinanceClient()
        print(f"[EngineManager] ✅ 공유 BinanceClient 생성 완료 (ID: {id(self._shared_binance_client)})")
        
        # 3개 엔진 초기화 (공유 클라이언트 주입)
        self._init_engines()
        
        print("[EngineManager] 엔진 매니저 초기화 완료")
    
    def _init_engines(self):
        """Alpha, Beta, Gamma 엔진 초기화 (공유 클라이언트 주입)"""
        try:
            # ✅ 동일한 BinanceClient 인스턴스를 모든 엔진에 주입
            self.engines["Alpha"] = AlphaStrategy(
                binance_client=self._shared_binance_client
            )
            self.engines["Beta"] = BetaStrategy(
                binance_client=self._shared_binance_client
            )
            self.engines["Gamma"] = GammaStrategy(
                binance_client=self._shared_binance_client
            )
            
            # 각 엔진의 초기 포지션 상태 설정
            for name, engine in self.engines.items():
                self._previous_position_states[name] = engine.in_position
                if hasattr(engine, "set_message_callback"):
                    engine.set_message_callback(lambda category, msg, engine_name=name: self._handle_strategy_message(engine_name, category, msg))
            
            print("[EngineManager] Alpha, Beta, Gamma 엔진 초기화 완료")
            print(f"[EngineManager] ✅ 모든 엔진이 공유 BinanceClient 사용 중")
        except Exception as e:
            print(f"[EngineManager] 엔진 초기화 오류: {e}")
    
    def add_message_callback(self, callback):
        """
        메시지 콜백 추가 (WebSocket 전송용)
        
        Args:
            callback: 메시지를 받을 콜백 함수
        """
        self._message_callbacks.append(callback)
    
    def _send_message(self, message_type: str, engine: Optional[str] = None, **kwargs):
        """
        GUI로 메시지 전송
        
        Args:
            message_type: 메시지 타입
            engine: 엔진 이름 (선택)
            **kwargs: 추가 데이터
        """
        message = {
            "type": message_type,
            **kwargs
        }
        
        if engine:
            message["engine"] = engine
        
        for callback in self._message_callbacks:
            try:
                callback(message)
            except Exception as e:
                print(f"[EngineManager] 메시지 전송 오류: {e}")
    
    def start_engine(self, engine_name: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        특정 엔진 시작
        
        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
            symbol: 거래 심볼 (선택사항, 예: "BTCUSDT")
            
        Returns:
            결과 딕셔너리
        """
        with self._lock:
            if engine_name not in self.engines:
                return {"success": False, "error": f"엔진 '{engine_name}'을 찾을 수 없습니다."}
            
            engine = self.engines[engine_name]
            
            if engine.is_running:
                return {"success": False, "error": f"{engine_name} 엔진이 이미 실행 중입니다."}
            
            # 심볼이 전달되면 Orchestrator 설정 업데이트
            if symbol and hasattr(engine, 'orchestrator') and hasattr(engine.orchestrator, 'cfg'):
                engine.orchestrator.cfg.symbol = symbol
                engine.current_symbol = symbol
                print(f"[EngineManager] {engine_name} 엔진 심볼 설정: {symbol}")
            
            # 엔진 시작
            success = engine.start()
            
            if success:
                self._send_message(
                    "ENGINE_MESSAGE",
                    engine=engine_name,
                    message=f"{engine_name} 엔진이 시작되었습니다."
                )
                
                self._send_message(
                    "ENGINE_STATUS_UPDATE",
                    engine=engine_name,
                    is_running=True
                )
                
                # 모니터링 스레드 시작 (첫 번째 엔진 시작 시)
                if not self._is_monitoring:
                    self._start_monitoring()
                
                return {"success": True}
            else:
                return {"success": False, "error": "엔진 시작 실패"}
    
    def stop_engine(self, engine_name: str) -> Dict[str, Any]:
        """
        특정 엔진 정지
        
        Args:
            engine_name: 엔진 이름
            
        Returns:
            결과 딕셔너리
        """
        with self._lock:
            if engine_name not in self.engines:
                return {"success": False, "error": f"엔진 '{engine_name}'을 찾을 수 없습니다."}
            
            engine = self.engines[engine_name]
            
            if not engine.is_running:
                return {"success": False, "error": f"{engine_name} 엔진이 실행 중이 아닙니다."}
            
            # 엔진 정지
            success = engine.stop()
            
            if success:
                self._send_message(
                    "ENGINE_MESSAGE",
                    engine=engine_name,
                    message=f"{engine_name} 엔진이 정지되었습니다."
                )
                
                self._send_message(
                    "ENGINE_STATUS_UPDATE",
                    engine=engine_name,
                    is_running=False
                )
                
                return {"success": True}
            else:
                return {"success": False, "error": "엔진 정지 실패"}
    
    def get_engine_status(self, engine_name: str) -> Optional[Dict[str, Any]]:
        """
        특정 엔진의 상태 조회
        
        Args:
            engine_name: 엔진 이름
            
        Returns:
            상태 딕셔너리 또는 None
        """
        if engine_name not in self.engines:
            return None
        
        return self.engines[engine_name].get_status()
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 엔진의 상태 조회
        
        Returns:
            엔진별 상태 딕셔너리
        """
        statuses = {}
        for name, engine in self.engines.items():
            statuses[name] = engine.get_status()
        return statuses
    
    def start_all_engines(self) -> List[Dict[str, Any]]:
        """
        모든 엔진 시작
        
        Returns:
            각 엔진의 시작 결과 리스트
        """
        results = []
        for name in self.engines.keys():
            result = self.start_engine(name)
            results.append({"engine": name, **result})
        return results
    
    def stop_all_engines(self) -> List[Dict[str, Any]]:
        """
        모든 엔진 정지
        
        Returns:
            각 엔진의 정지 결과 리스트
        """
        results = []
        for name in self.engines.keys():
            result = self.stop_engine(name)
            results.append({"engine": name, **result})
        
        # 모든 엔진 정지 시 모니터링도 중지
        if self._is_monitoring:
            self._stop_monitoring()
        
        return results
    
    def _start_monitoring(self):
        """엔진 상태 모니터링 스레드 시작"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("[EngineManager] 모니터링 스레드 시작")
    
    def _stop_monitoring(self):
        """엔진 상태 모니터링 스레드 정지"""
        self._is_monitoring = False
        print("[EngineManager] 모니터링 스레드 정지")
    
    def _monitor_loop(self):
        """
        엔진 상태 모니터링 루프
        
        주기적으로 각 엔진의 상태를 확인하고 GUI로 전송
        """
        print("[EngineManager] 모니터링 루프 시작")
        
        while self._is_monitoring:
            try:
                # 실행 중인 엔진이 있는지 확인
                any_running = any(engine.is_running for engine in self.engines.values())
                
                if not any_running:
                    time.sleep(2)
                    continue
                
                # 각 엔진의 상태 업데이트
                for name, engine in self.engines.items():
                    if engine.is_running:
                        status = engine.get_status()
                        
                        # 거래 종료 감지 (포지션이 있었는데 사라진 경우)
                        previous_in_position = self._previous_position_states.get(name, False)
                        current_in_position = engine.in_position
                        
                        if previous_in_position and not current_in_position:
                            # 포지션이 종료됨 - 실현 손익 전달
                            realized_pnl = engine.get_realized_pnl()
                            if realized_pnl != 0:
                                self._handle_position_closed(name, realized_pnl)
                        
                        # 포지션 상태 업데이트
                        self._previous_position_states[name] = current_in_position
                        
                        # 통계 업데이트 전송
                        self._send_message(
                            "ENGINE_STATS_UPDATE",
                            engine=name,
                            data={
                                "symbol": status.get("symbol", "-"),
                                "pnl_percent": status.get("pnl_percent", 0.0),
                                "total_trades": status.get("total_trades", 0),
                                "realized_pnl": engine.get_realized_pnl(),
                                "total_gain_loss": engine.get_realized_pnl(),
                                "designated_funds": getattr(engine, "designated_funds", 0.0),
                            }
                        )
                
                time.sleep(3)  # 3초마다 업데이트
                
            except Exception as e:
                print(f"[EngineManager] 모니터링 루프 오류: {e}")
                time.sleep(5)
        
        print("[EngineManager] 모니터링 루프 종료")
    
    def _handle_position_closed(self, engine_name: str, realized_pnl: float):
        """
        포지션 종료 처리
        
        Args:
            engine_name: 엔진 이름
            realized_pnl: 실현 손익 (USDT)
        """
        print(f"[EngineManager] {engine_name} 엔진 포지션 종료 감지: 실현 손익 {realized_pnl:.2f} USDT")
        
        # 엔진 상태 조회 (거래 기록 저장용)
        engine = self.engines.get(engine_name)
        if engine:
            status = engine.get_status()
            symbol = status.get("symbol", "")
            designated_funds = engine.designated_funds
            leverage = engine.config.get("leverage", 1)
            pnl_percent = engine._calculate_pnl_percent()
            
            # 거래 기록 DB 저장 (별도 스레드에서 비동기 실행)
            threading.Thread(
                target=self._save_trade_record_sync,
                args=(engine_name, symbol, designated_funds, leverage, realized_pnl, pnl_percent),
                daemon=True
            ).start()
        
        # 실현 손익 콜백 호출
        if self._realized_pnl_callback:
            try:
                self._realized_pnl_callback(engine_name, realized_pnl)
            except Exception as e:
                print(f"[EngineManager] 실현 손익 콜백 호출 오류: {e}")
        
        # 메시지 전송 (GUI 업데이트용)
        self._send_message(
            "ENGINE_TRADE_COMPLETED",
            engine=engine_name,
            data={
                "symbol": symbol if engine else "",
                "funds": designated_funds if engine else 0.0,
                "leverage": leverage if engine else 1,
                "profit_loss": realized_pnl,
                "pnl_percent": pnl_percent if engine else 0.0
            }
        )
    
    def _handle_strategy_message(self, engine_name: str, category: str, message: str):
        """전략에서 올라온 메시지를 GUI로 전달"""
        if not message:
            return
        self._send_message(
            "ENGINE_STATUS_MESSAGE",
            engine=engine_name,
            category=category,
            message=message
        )
    
    def _save_trade_record_sync(
        self, engine_name: str, symbol: str, funds: float, 
        leverage: int, profit_loss: float, pnl_percent: float
    ) -> None:
        """
        거래 기록을 DB에 저장 (동기 버전 - 스레드에서 실행)
        
        Args:
            engine_name: 엔진 이름
            symbol: 코인 심볼
            funds: 투입 자금
            leverage: 레버리지
            profit_loss: 수익/손실
            pnl_percent: P&L %
        """
        if not symbol:
            return
        
        try:
            # 비동기 함수를 동기적으로 실행
            asyncio.run(self._save_trade_record(
                engine_name, symbol, funds, leverage, profit_loss, pnl_percent
            ))
        except Exception as e:
            print(f"[EngineManager] 거래 기록 저장 스레드 오류: {e}")
    
    async def _save_trade_record(
        self, engine_name: str, symbol: str, funds: float, 
        leverage: int, profit_loss: float, pnl_percent: float
    ) -> None:
        """
        거래 기록을 DB에 저장 (비동기)
        
        Args:
            engine_name: 엔진 이름
            symbol: 코인 심볼
            funds: 투입 자금
            leverage: 레버리지
            profit_loss: 수익/손실
            pnl_percent: P&L %
        """
        if not symbol:
            return
        
        try:
            # 현재 시간 (거래 일시)
            trade_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            created_at_utc = datetime.utcnow().isoformat()

            # 1) 메인 백엔드의 로컬 DB에 저장
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO trade_history (
                        engine_name, symbol, trade_datetime, funds, leverage,
                        profit_loss, pnl_percent, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        engine_name,
                        symbol,
                        trade_datetime,
                        funds,
                        leverage,
                        profit_loss,
                        pnl_percent,
                        created_at_utc,
                    ),
                )
                await db.commit()
                print(f"[EngineManager] 거래 기록 저장 완료: {engine_name} - {symbol}")

            # 2) 옵션: 엔진 백엔드에도 동일 히스토리를 전송해 동기화
            if ENABLE_ENGINE_EXECUTOR and ENGINE_EXECUTOR_URL:
                try:
                    payload = {
                        "engine_name": engine_name,
                        "symbol": symbol,
                        "trade_datetime": trade_datetime,
                        "funds": float(funds),
                        "leverage": int(leverage),
                        "profit_loss": float(profit_loss),
                        "pnl_percent": float(pnl_percent),
                        "entry_price": None,
                        "exit_price": None,
                        "position_side": None,
                    }
                    url = ENGINE_EXECUTOR_URL.rstrip("/") + "/internal/v1/trade-history"
                    # 동기 요청이지만, 실패해도 전체 흐름에 영향 주지 않도록 예외만 로깅
                    resp = requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=2.0)
                    if resp.status_code >= 400:
                        print(f"[EngineManager] 엔진 백엔드 trade_history 동기화 실패: {resp.status_code} {resp.text}")
                except Exception as sync_err:
                    print(f"[EngineManager] 엔진 백엔드 trade_history 동기화 예외: {sync_err}")
        except Exception as e:
            print(f"[EngineManager] 거래 기록 저장 실패: {e}")
    
    def set_engine_designated_funds(self, engine_name: str, amount: float):
        """
        엔진의 배분 자금 설정
        
        Args:
            engine_name: 엔진 이름
            amount: 배분 금액 (USDT)
        """
        if engine_name in self.engines:
            self.engines[engine_name].set_designated_funds(max(amount, 0.0))
            print(f"[EngineManager] {engine_name} 엔진 배분 자금 설정: {amount:.2f} USDT")
    
    def shutdown(self):
        """엔진 매니저 종료 (리소스 정리)"""
        print("[EngineManager] 종료 중...")
        self.stop_all_engines()
        self._is_monitoring = False
        
        # ✅ 공유 BinanceClient 정리
        if hasattr(self, '_shared_binance_client'):
            if hasattr(self._shared_binance_client, 'session'):
                try:
                    self._shared_binance_client.session.close()
                    print("[EngineManager] ✅ 공유 BinanceClient 세션 정리 완료")
                except Exception as e:
                    print(f"[EngineManager] BinanceClient 세션 정리 오류: {e}")
        
        print("[EngineManager] 종료 완료")


# 싱글톤 인스턴스
_engine_manager_instance = None


def get_engine_manager(db_path: Optional[str] = None) -> EngineManager:
    """
    엔진 매니저 싱글톤 인스턴스 반환
    
    Args:
        db_path: 데이터베이스 파일 경로 (거래 기록 저장용, 선택적)
    
    Returns:
        EngineManager 인스턴스
    """
    global _engine_manager_instance
    if _engine_manager_instance is None:
        _engine_manager_instance = EngineManager(db_path=db_path)
    return _engine_manager_instance

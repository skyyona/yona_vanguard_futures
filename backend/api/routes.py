from fastapi import APIRouter, Depends, HTTPException, Body
from starlette.requests import Request
from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional, Dict, List, Any, Tuple
import logging
from datetime import datetime, timedelta
from asyncio import Semaphore
from backend.core.yona_service import YonaService
from backend.core.engine_manager import get_engine_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# ========================================
# 백테스트 캐싱 & 동시 실행 제한
# ========================================

# 백테스트 결과 캐시 (메모리)
backtest_result_cache: Dict[str, Dict] = {}
MAX_CACHE_SIZE = 100  # 최대 100개 심볼 결과 저장

# 동시 백테스트 제한 (최대 3개)
backtest_semaphore = Semaphore(3)

# 요청 모델
class EngineControlRequest(BaseModel):
    engine: str  # "Alpha", "Beta", "Gamma"
    symbol: Optional[str] = None  # 선택적 심볼 (엔진 시작 시 사용)

class SetFixedTimeRequest(BaseModel):
    fixed_time: Optional[str] = None  # ISO 형식 문자열 또는 None

class BlacklistSymbols(BaseModel):
    symbols: List[str]
    status: str = "MANUAL"

    @field_validator('symbols')
    @classmethod
    def symbols_must_not_be_empty(cls, v):
        if not v or not isinstance(v, list) or not all(isinstance(s, str) and s for s in v):
            raise ValueError('symbols must be a non-empty list of non-empty strings')
        return v

class NewStrategyStartRequest(BaseModel):
    symbol: str
    leverage: int = 10
    quantity: Optional[float] = None

class NewStrategyStopRequest(BaseModel):
    force: bool = False  # True: 포지션 보유 시에도 강제 종료

# FastAPI의 의존성 주입 시스템을 올바르게 사용
def get_yona_service(request: Request) -> YonaService:
    return request.app.state.yona_service

@router.post("/start")
async def start_analysis(service: YonaService = Depends(get_yona_service)):
    """분석 및 자동매매 엔진을 시작합니다."""
    await service.start_analysis()
    return {"status": "success", "message": "Analysis and trading engines started."}

@router.post("/stop")
async def stop_analysis(service: YonaService = Depends(get_yona_service)):
    """분석 및 자동매매 엔진을 중지합니다 (긴급 청산 없이)."""
    await service.stop_analysis()
    return {"status": "success", "message": "Analysis and trading engines stopped."}

@router.post("/emergency/liquidate")
async def emergency_liquidate(service: YonaService = Depends(get_yona_service)):
    """긴급 포지션 청산 - 모든 활성 포지션을 시장가로 즉시 청산합니다."""
    await service.emergency_liquidate()
    return {"status": "success", "message": "Emergency liquidation initiated."}

@router.post("/set-fixed-time")
async def set_fixed_time(request: SetFixedTimeRequest, service: YonaService = Depends(get_yona_service)):
    """
    시간 고정/해제 설정
    
    Request Body:
        {"fixed_time": "2024-01-01T12:00:00"} - 시간 고정
        {"fixed_time": null} - 시간 고정 해제
    """
    await service.set_fixed_time(request.fixed_time)
    
    if request.fixed_time:
        return {"status": "success", "message": f"Time fixed at {request.fixed_time}"}
    else:
        return {"status": "success", "message": "Time fixed cleared"}

# 블랙리스트 엔드포인트
@router.get("/live/blacklist")
async def list_blacklist(service: YonaService = Depends(get_yona_service)):
    """블랙리스트 목록 조회"""
    items = await service.list_blacklist()
    return {"status": "ok", "data": items}

@router.post("/live/blacklist/add")
async def add_blacklist(payload: dict = Body(...), service: YonaService = Depends(get_yona_service)):
    """블랙리스트에 심볼 추가"""
    try:
        data = BlacklistSymbols(**payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    await service.add_blacklist(data.symbols, data.status)
    return {"status": "ok"}

@router.post("/live/blacklist/remove")
async def remove_blacklist(payload: dict = Body(...), service: YonaService = Depends(get_yona_service)):
    """블랙리스트에서 심볼 제거"""
    try:
        data = BlacklistSymbols(**payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    await service.remove_blacklist(data.symbols)
    return {"status": "ok"}

@router.get("/live/analysis/entry")
async def analyze_entry(symbol: str, service: YonaService = Depends(get_yona_service)):
    """포지션 진입 타이밍 분석"""
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    try:
        data = await service.analyze_entry_timing(symbol.upper().strip())
        return {"status": "ok", "data": data}
    except Exception as e:
        # 오류 발생 시에도 기본 데이터 반환 (GUI가 중단되지 않도록)
        return {
            "status": "ok",
            "data": {
                "symbol": symbol,
                "score": 0,
                "message": f"analysis unavailable: {str(e)}"
            }
        }

# 엔진 제어 엔드포인트
@router.post("/engine/start")
async def start_engine(request: EngineControlRequest):
    """
    특정 엔진 시작
    
    Request Body:
        {"engine": "Alpha", "symbol": "BTCUSDT"}  # symbol은 선택사항
    """
    engine_manager = get_engine_manager()
    
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
    
    result = engine_manager.start_engine(request.engine, symbol=request.symbol)
    
    if result.get("success"):
        return {"status": "success", "message": f"{request.engine} engine started."}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

@router.post("/engine/stop")
async def stop_engine(request: EngineControlRequest):
    """
    특정 엔진 정지
    
    Request Body:
        {"engine": "Alpha"}
    """
    engine_manager = get_engine_manager()
    
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
    
    result = engine_manager.stop_engine(request.engine)
    
    if result.get("success"):
        return {"status": "success", "message": f"{request.engine} engine stopped."}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

@router.get("/engine/status/{engine_name}")
async def get_engine_status(engine_name: str):
    """
    특정 엔진의 상태 조회
    
    Path Parameter:
        engine_name: "Alpha", "Beta", or "Gamma"
    """
    engine_manager = get_engine_manager()
    
    if engine_name not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
    
    status = engine_manager.get_engine_status(engine_name)
    
    if status is None:
        raise HTTPException(status_code=404, detail="Engine not found.")
    
    return {"status": "success", "data": status}

@router.get("/engine/status")
async def get_all_engine_statuses():
    """모든 엔진의 상태 조회"""
    engine_manager = get_engine_manager()
    statuses = engine_manager.get_all_statuses()
    return {"status": "success", "data": statuses}

# 자금 배분 관리 엔드포인트
class FundsAllocationRequest(BaseModel):
    engine: str  # "NewModular"
    amount: float  # 배분 금액 (USDT)

class EngineLeverageRequest(BaseModel):
    engine: str  # "NewModular"
    leverage: int  # 1~125

class EngineSymbolRequest(BaseModel):
    engine: str  # "NewModular"
    symbol: str  # e.g., "BTCUSDT"

class EnginePrepareSymbolRequest(BaseModel):
    engine: str  # "Alpha", "Beta", "Gamma"
    symbol: str  # e.g., "TNSRUSDT"
    leverage: int  # 1~125

@router.post("/funds/allocation/set")
async def set_funds_allocation(request: FundsAllocationRequest, service: YonaService = Depends(get_yona_service)):
    """
    특정 엔진의 배분 자금 설정
    
    Request Body:
        {"engine": "NewModular", "amount": 3000.0}
    """
    try:
        await service.set_funds_allocation(request.engine, request.amount)
        return {"status": "success", "message": f"{request.engine} 엔진 배분 자금 설정: {request.amount:.2f} USDT"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/funds/allocation/remove")
async def remove_funds_allocation(request: EngineControlRequest, service: YonaService = Depends(get_yona_service)):
    """
    특정 엔진의 배분 자금 제거
    
    Request Body:
        {"engine": "NewModular"}
    """
    try:
        await service.remove_funds_allocation(request.engine)
        return {"status": "success", "message": f"{request.engine} 엔진 배분 자금 제거 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/engine/symbol")
async def set_engine_symbol(request: EngineSymbolRequest, service: YonaService = Depends(get_yona_service)):
    """
    특정 엔진의 거래 심볼을 설정합니다.

    Request Body:
        {"engine": "NewModular", "symbol": "BTCUSDT"}
    """
    if request.engine not in ["NewModular"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'NewModular'.")
    symbol = (request.symbol or "").upper().strip()
    if not symbol or not symbol.endswith("USDT"):
        raise HTTPException(status_code=400, detail="Invalid symbol. Must be a non-empty USDT perpetual symbol.")
    try:
        await service.update_engine_symbol(request.engine, symbol)
        return {"status": "success", "message": f"{request.engine} 심볼 설정: {symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/funds/allocation/return")
async def return_funds_allocation(request: EngineControlRequest, service: YonaService = Depends(get_yona_service)):
    """
    특정 엔진의 운용 자금을 Available Funds로 반환
    """
    try:
        returned_amount = await service.return_funds(request.engine)
        return {
            "status": "success",
            "message": f"{request.engine} 엔진 자금이 반환되었습니다.",
            "data": {"returned_amount": returned_amount}
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/funds/allocation")
async def get_funds_allocations(service: YonaService = Depends(get_yona_service)):
    """모든 엔진의 배분 자금 조회"""
    allocations = await service.get_funds_allocations()
    return {"status": "success", "data": allocations}

@router.get("/account/total-balance")
async def get_account_total_balance(service: YonaService = Depends(get_yona_service)):
    """Account total balance 조회 (배분 차감 후 잔액)"""
    balance = await service.get_account_total_balance()
    return {"status": "success", "data": {"total_balance": balance}}

@router.post("/account/initial/reset")
async def reset_initial_investment(service: YonaService = Depends(get_yona_service)):
    """현재 선물 계정 잔고를 기준으로 Initial Investment를 재설정"""
    try:
        new_amount = await service.reset_initial_investment()
        return {"status": "success", "data": {"initial_investment": new_amount}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/engine/leverage")
async def set_engine_leverage(request: EngineLeverageRequest, service: YonaService = Depends(get_yona_service)):
    """
    특정 엔진의 런타임 레버리지를 동기화합니다.

    Request Body:
        {"engine": "Alpha"|"Beta"|"Gamma", "leverage": 1..125}
    """
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
    try:
        await service.update_engine_leverage(request.engine, request.leverage)
        return {"status": "success", "message": f"{request.engine} 레버리지 {request.leverage}x 적용"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/engine/prepare-symbol")
async def prepare_engine_symbol(request: EnginePrepareSymbolRequest):
    """
    엔진의 심볼을 Binance에 준비 (마진 타입 + 레버리지 설정)
    
    "설정 적용" 버튼에서 호출하여 Binance 선물 거래 페이지에 설정 적용
    
    Request Body:
        {"engine": "Alpha", "symbol": "TNSRUSDT", "leverage": 30}
    """
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
    
    from backend.core.engine_manager import get_engine_manager
    engine_manager = get_engine_manager()
    
    engine = engine_manager.engines.get(request.engine)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Engine {request.engine} not found.")
    
    if not hasattr(engine, 'orchestrator') or not hasattr(engine.orchestrator, 'exec'):
        raise HTTPException(status_code=500, detail="Engine orchestrator not initialized.")
    
    # Orchestrator config 업데이트
    engine.orchestrator.cfg.symbol = request.symbol
    engine.orchestrator.cfg.leverage = request.leverage
    engine.current_symbol = request.symbol
    
    # Binance에 마진 타입 + 레버리지 설정
    ok = engine.orchestrator.exec.prepare_symbol(
        request.symbol, 
        request.leverage, 
        engine.orchestrator.cfg.isolated_margin
    )
    
    if ok:
        logger.info(f"✅ {request.engine} 엔진 심볼 준비 완료: {request.symbol} @ {request.leverage}x")
        return {
            "status": "success", 
            "message": f"{request.engine} 심볼 준비 완료: {request.symbol} @ {request.leverage}x"
        }
    else:
        logger.error(f"❌ {request.engine} 엔진 심볼 준비 실패: {request.symbol}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to prepare {request.symbol} (margin/leverage setup error)"
        )


# ==================== NewStrategy 전용 엔드포인트 ====================
# 싱글톤 인스턴스 관리 (추후 Redis로 전환 가능)
_new_strategy_instance: Optional[Any] = None

@router.post("/strategy/new/start")
async def start_new_strategy(request: NewStrategyStartRequest, service: YonaService = Depends(get_yona_service)):
    """
    NewStrategy (모듈형 고도화 전략)를 시작합니다.

    Request Body:
        {
            "symbol": "BTCUSDT",
            "leverage": 10,
            "quantity": 0.001  // Optional, None이면 RiskManager가 자동 계산
        }
    """
    global _new_strategy_instance
    
    if _new_strategy_instance is not None and getattr(_new_strategy_instance, "is_running", False):
        raise HTTPException(status_code=400, detail="NewStrategy is already running. Stop it first.")
    
    try:
        from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper
        from backend.api_client.binance_client import BinanceClient
        
        # BinanceClient 인스턴스 생성 (YonaService에서 재사용 가능하면 그쪽 사용 권장)
        binance_client = BinanceClient()
        
        # Wrapper 초기화
        _new_strategy_instance = NewStrategyWrapper(
            binance_client=binance_client,
            symbol=request.symbol,
            leverage=request.leverage,
            quantity=request.quantity
        )
        
        # 전략 시작 (백그라운드 스레드)
        _new_strategy_instance.start()
        
        return {
            "status": "success",
            "message": f"NewStrategy started for {request.symbol} at {request.leverage}x leverage",
            "data": _new_strategy_instance.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NewStrategy: {str(e)}")


@router.get("/strategy/new/status")
async def get_new_strategy_status():
    """
    NewStrategy의 현재 상태를 조회합니다.

    Response:
        {
            "is_running": bool,
            "engine_name": "NewModular",
            "symbol": str,
            "leverage": int,
            "position": {...},
            "last_signal": {...},
            "orchestrator_running": bool
        }
    """
    global _new_strategy_instance
    
    if _new_strategy_instance is None:
        return {
            "is_running": False,
            "engine_name": "NewModular",
            "message": "NewStrategy has not been started yet."
        }
    
    try:
        status = _new_strategy_instance.get_status()
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/strategy/new/stop")
async def stop_new_strategy(request: NewStrategyStopRequest = NewStrategyStopRequest()):
    """
    NewStrategy를 중지합니다.

    Request Body:
        {
            "force": false  // true이면 포지션 보유 시에도 강제 종료
        }
    """
    global _new_strategy_instance
    
    if _new_strategy_instance is None:
        raise HTTPException(status_code=400, detail="NewStrategy is not running.")
    
    try:
        # 포지션 체크
        status = _new_strategy_instance.get_status()
        has_position = status.get("position", {}).get("quantity", 0) != 0
        
        if has_position and not request.force:
            return {
                "status": "warning",
                "message": "Strategy has open position. Set 'force=true' to stop anyway.",
                "position": status.get("position")
            }
        
        # 전략 중지
        _new_strategy_instance.stop()
        _new_strategy_instance = None
        
        return {
            "status": "success",
            "message": "NewStrategy stopped successfully.",
            "had_position": has_position
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop NewStrategy: {str(e)}")


# ========================================
# 백테스팅 API - 거래 적합성 평가
# ========================================

def get_cache_key(symbol: str, period: str) -> str:
    """
    캐시 키 생성
    
    Args:
        symbol: 코인 심볼 (예: "GRASSUSDT")
        period: 백테스트 기간 ("1w" or "1m")
    
    Returns:
        캐시 키 (예: "GRASSUSDT_1w_2025-11-20")
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{symbol}_{period}_{today}"


def evaluate_suitability(results: Dict) -> Tuple[str, float]:
    """
    백테스트 결과로 거래 적합성 판단
    
    평가 기준:
    1. 승률 (30점)
       - >=70%: 30점
       - >=50%: 20점
       - >=40%: 10점
    
    2. 수익률 (40점)
       - >=+5%: 40점
       - >=+2%: 30점
       - >=0%: 15점
    
    3. 최대 낙폭 MDD (20점)
       - <=3%: 20점
       - <=5%: 15점
       - <=10%: 10점
    
    4. 거래 횟수 (10점)
       - >=5회: 10점
       - >=3회: 5점
    
    최종 판단:
    - 적합: 70점 이상 + 승률>=50% + 수익률>=+2%
    - 주의 필요: 50점 이상
    - 부적합: 50점 미만
    
    Args:
        results: 백테스트 메트릭 딕셔너리
    
    Returns:
        Tuple[적합성 문자열, 점수]
    """
    score = 0.0
    
    # 1. 승률 평가 (30점)
    win_rate = results.get("win_rate", 0)
    if win_rate >= 70:
        score += 30
    elif win_rate >= 50:
        score += 20
    elif win_rate >= 40:
        score += 10
    
    # 2. 수익률 평가 (40점)
    pnl_pct = results.get("total_pnl_pct", 0)
    if pnl_pct >= 5:
        score += 40
    elif pnl_pct >= 2:
        score += 30
    elif pnl_pct >= 0:
        score += 15
    
    # 3. 최대 낙폭 평가 (20점)
    mdd = results.get("max_drawdown", 100)
    if mdd <= 3:
        score += 20
    elif mdd <= 5:
        score += 15
    elif mdd <= 10:
        score += 10
    
    # 4. 거래 횟수 평가 (10점)
    trades = results.get("total_trades", 0)
    if trades >= 5:
        score += 10
    elif trades >= 3:
        score += 5
    
    # 최종 적합성 판단
    if score >= 70 and win_rate >= 50 and pnl_pct >= 2:
        suitability = "적합"
    elif score >= 50:
        suitability = "주의 필요"
    else:
        suitability = "부적합"
    
    logger.info(f"[SUITABILITY] {suitability} ({score:.0f}점) - "
                f"승률={win_rate:.1f}%, 수익률={pnl_pct:+.2f}%, MDD={mdd:.1f}%")
    
    return suitability, score


def generate_reason(results: Dict) -> str:
    """
    적합성 판단 근거 생성
    
    Args:
        results: 백테스트 메트릭
    
    Returns:
        근거 문자열 (예: "승률 60.0%, 수익률 +5.20%, 거래 10회, MDD 3.5%")
    """
    win_rate = results.get("win_rate", 0)
    pnl_pct = results.get("total_pnl_pct", 0)
    trades = results.get("total_trades", 0)
    mdd = results.get("max_drawdown", 0)
    
    return (
        f"승률 {win_rate:.1f}%, "
        f"수익률 {pnl_pct:+.2f}%, "
        f"거래 {trades}회, "
        f"MDD {mdd:.1f}%"
    )


@router.get("/backtest/suitability")
async def get_trading_suitability(
    symbol: str,
    period: str = "1w"  # "1w" (1주) or "1m" (1달)
):
    """
    코인 심볼의 거래 적합성 평가 (백테스팅)
    
    API 최적화:
    1. 메모리 캐싱: 동일 심볼+기간+날짜 → 캐시 반환 (API 호출 0번)
    2. 우선순위 큐: 최대 3개 동시 백테스트 실행 (Rate Limit 방지)
    
    Args:
        symbol: 코인 심볼 (예: "GRASSUSDT")
        period: 백테스트 기간 ("1w" = 1주, "1m" = 1달)
    
    Returns:
        {
            "success": true,
            "cached": true/false,
            "data": {
                "symbol": "GRASSUSDT",
                "period": "1w",
                "suitability": "적합" | "부적합" | "주의 필요",
                "score": 75.5,
                "reason": "승률 60%, 수익률 +5.2%, 거래 10회, MDD 3.5%",
                "metrics": {...}
            }
        }
    """
    # ========================================
    # 1. 캐시 확인 (메모리)
    # ========================================
    cache_key = get_cache_key(symbol, period)
    
    if cache_key in backtest_result_cache:
        logger.info(f"✅ [CACHE HIT] {cache_key}")
        return {
            "success": True,
            "cached": True,
            "data": backtest_result_cache[cache_key]
        }
    
    logger.info(f"🔄 [CACHE MISS] {cache_key} - 백테스트 실행")
    
    # ========================================
    # 2. 우선순위 큐 (동시 실행 제한)
    # ========================================
    async with backtest_semaphore:
        try:
            # 3. 백테스트 기간 계산
            end_date = datetime.now()
            if period == "1w":
                start_date = end_date - timedelta(days=7)
            elif period == "1m":
                start_date = end_date - timedelta(days=30)
            else:
                return {
                    "success": False,
                    "error": f"Invalid period: {period} (use '1w' or '1m')"
                }
            
            # 4. BacktestConfig 생성
            from backend.core.new_strategy.backtest_adapter import BacktestConfig
            config = BacktestConfig(
                symbol=symbol,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                initial_balance=10000.0,
                leverage=50,
                commission_rate=0.0004,
                slippage_rate=0.0001,
            )
            
            # 5. 공유 BinanceClient 가져오기
            engine_manager = get_engine_manager()
            shared_binance_client = engine_manager._shared_binance_client
            
            # 6. Orchestrator 생성 (Alpha 전략)
            from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
            orchestrator = StrategyOrchestrator(
                binance_client=shared_binance_client,
                config=OrchestratorConfig(
                    symbol=symbol,
                    leverage=50,
                    order_quantity=0.001,
                    enable_trading=False,  # 백테스트는 실거래 안함
                )
            )
            
            # 7. 백테스트 실행
            logger.info(f"[BACKTEST] 시작: {symbol} ({period}) - {config.start_date} ~ {config.end_date}")
            
            from backend.core.new_strategy.backtest_adapter import BacktestAdapter
            adapter = BacktestAdapter(shared_binance_client)
            results = adapter.run_backtest(orchestrator, config)
            
            logger.info(f"[BACKTEST] 완료: {symbol} - {results.get('total_trades', 0)}건 거래")
            
            # 8. 적합성 평가
            suitability, score = evaluate_suitability(results)
            reason = generate_reason(results)
            
            # 9. 응답 데이터 생성
            response_data = {
                "symbol": symbol,
                "period": period,
                "suitability": suitability,
                "score": score,
                "reason": reason,
                "metrics": results
            }
            
            # ========================================
            # 10. 캐시 저장 (LRU: 가장 오래된 항목 제거)
            # ========================================
            if len(backtest_result_cache) >= MAX_CACHE_SIZE:
                oldest_key = next(iter(backtest_result_cache))
                removed = backtest_result_cache.pop(oldest_key)
                logger.info(f"[CACHE] LRU 제거: {oldest_key}")
            
            backtest_result_cache[cache_key] = response_data
            logger.info(f"💾 [CACHE SAVED] {cache_key} (캐시 크기: {len(backtest_result_cache)})")
            
            return {
                "success": True,
                "cached": False,
                "data": response_data
            }
        
        except Exception as e:
            logger.error(f"❌ [BACKTEST ERROR] {symbol}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# ========================================
# 전략 분석 API - 3개 엔진별 백테스팅 및 전략 분석
# ========================================

async def calculate_volatility(symbol: str, binance_client) -> float:
    """
    코인의 변동성 계산 (24시간 기준)
    
    Args:
        symbol: 코인 심볼
        binance_client: BinanceClient 인스턴스
    
    Returns:
        변동성 (%)
    """
    try:
        # 24시간 티커 데이터 조회
        ticker_data = binance_client.get_24hr_ticker(symbol)
        
        if isinstance(ticker_data, dict) and "error" in ticker_data:
            logger.warning(f"[VOLATILITY] 티커 데이터 조회 실패: {symbol}")
            return 0.0
        
        if isinstance(ticker_data, list):
            # 모든 심볼 데이터에서 해당 심볼 찾기
            for ticker in ticker_data:
                if ticker.get("symbol") == symbol:
                    ticker_data = ticker
                    break
            else:
                logger.warning(f"[VOLATILITY] 심볼을 찾을 수 없음: {symbol}")
                return 0.0
        
        # 변동성 계산: (고가 - 저가) / 현재가 * 100
        high_price = float(ticker_data.get("highPrice", 0))
        low_price = float(ticker_data.get("lowPrice", 0))
        current_price = float(ticker_data.get("lastPrice", 0))
        
        if current_price == 0:
            logger.warning(f"[VOLATILITY] 현재가가 0: {symbol}")
            return 0.0
        
        volatility = ((high_price - low_price) / current_price) * 100
        return round(volatility, 2)
    
    except Exception as e:
        logger.error(f"[VOLATILITY] 변동성 계산 오류: {symbol} - {e}")
        return 0.0


def calculate_max_target_profit(
    engine_name: str,
    volatility: float,
    backtest_results: Dict[str, Any]
) -> float:
    """
    변동성 기반 최대 목표 수익률% 계산
    
    Args:
        engine_name: 엔진명 ("Alpha", "Beta", "Gamma")
        volatility: 변동성 (%)
        backtest_results: 백테스트 결과
    
    Returns:
        최대 목표 수익률%
    """
    # 엔진별 기본 익절률
    base_profit = {
        "Alpha": 3.7,
        "Beta": 5.0,
        "Gamma": 8.5
    }
    
    # 변동성 기반 조정 (변동성의 배수)
    volatility_multiplier = {
        "Alpha": 1.5,  # 변동성의 1.5배
        "Beta": 2.0,   # 변동성의 2.0배
        "Gamma": 3.0   # 변동성의 3.0배
    }
    
    base = base_profit.get(engine_name, 3.7)
    multiplier = volatility_multiplier.get(engine_name, 1.5)
    
    # 변동성 기반 계산 (최대 기본 익절률 제한)
    volatility_based = volatility * multiplier
    max_profit = min(base, volatility_based)
    
    # 백테스트 결과 반영 (예상 수익률의 80%를 안전 마진으로 설정)
    expected_profit = backtest_results.get("total_pnl_pct", 0)
    if expected_profit > 0:
        max_profit = min(max_profit, expected_profit * 0.8)
    
    return round(max_profit, 2)


@router.get("/backtest/strategy-analysis")
async def get_strategy_analysis(
    symbol: str,
    period: str = "1w"  # "1w" (1주) or "1m" (1달)
):
    """
    코인 심볼에 대한 전략 분석 (3개 엔진별 백테스팅)
    
    Args:
        symbol: 코인 심볼 (예: "BTCUSDT")
        period: 백테스트 기간 ("1w" = 1주, "1m" = 1달)
    
    Returns:
        {
            "success": true,
            "data": {
                "symbol": "BTCUSDT",
                "best_engine": "Alpha",
                "volatility": 2.5,
                "max_target_profit": {
                    "alpha": 3.7,
                    "beta": 5.0,
                    "gamma": 8.5
                },
                "risk_management": {
                    "stop_loss": 0.5,
                    "trailing_stop": 0.3
                },
                "engine_results": {
                    "alpha": {...},
                    "beta": {...},
                    "gamma": {...}
                }
            }
        }
    """
    logger.info(f"[STRATEGY_ANALYSIS] 시작: {symbol} ({period})")
    
    try:
        # 1. 공유 BinanceClient 가져오기
        engine_manager = get_engine_manager()
        shared_binance_client = engine_manager._shared_binance_client
        
        # 2. 변동성 계산
        volatility = await calculate_volatility(symbol, shared_binance_client)
        logger.info(f"[STRATEGY_ANALYSIS] 변동성: {symbol} = {volatility:.2f}%")
        
        # 3. 백테스트 기간 계산
        end_date = datetime.now()
        if period == "1w":
            start_date = end_date - timedelta(days=7)
        elif period == "1m":
            start_date = end_date - timedelta(days=30)
        else:
            return {
                "success": False,
                "error": f"Invalid period: {period} (use '1w' or '1m')"
            }
        
        # 4. 3개 엔진별 백테스팅 실행
        engine_results = {}
        
        # 엔진별 기본 설정
        engine_configs = {
            "Alpha": {"leverage": 5, "order_quantity": 0.001, "timeframe": "1m"},
            "Beta": {"leverage": 3, "order_quantity": 0.001, "timeframe": "5m"},
            "Gamma": {"leverage": 2, "order_quantity": 0.001, "timeframe": "1h"}
        }
        
        for engine_name in ["Alpha", "Beta", "Gamma"]:
            try:
                logger.info(f"[STRATEGY_ANALYSIS] {engine_name} 엔진 백테스팅 시작: {symbol}")
                
                config = engine_configs[engine_name]
                
                # BacktestConfig 생성
                from backend.core.new_strategy.backtest_adapter import BacktestConfig
                backtest_config = BacktestConfig(
                    symbol=symbol,
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    initial_balance=10000.0,
                    leverage=config["leverage"],
                    commission_rate=0.0004,
                    slippage_rate=0.0001,
                )
                
                # Orchestrator 생성
                from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
                orchestrator_config = OrchestratorConfig(
                    symbol=symbol,
                    leverage=config["leverage"],
                    order_quantity=config["order_quantity"],
                    enable_trading=False,  # 백테스트는 실거래 안함
                )
                
                orchestrator = StrategyOrchestrator(
                    binance_client=shared_binance_client,
                    config=orchestrator_config
                )
                
                # 백테스트 실행
                from backend.core.new_strategy.backtest_adapter import BacktestAdapter
                adapter = BacktestAdapter(shared_binance_client)
                results = adapter.run_backtest(orchestrator, backtest_config)
                
                # 적합성 평가
                suitability, score = evaluate_suitability(results)
                
                # 변동성 기반 최대 목표 수익률% 계산
                max_target_profit = calculate_max_target_profit(
                    engine_name, volatility, results
                )
                
                engine_results[engine_name.lower()] = {
                    "suitability": suitability,
                    "score": score,
                    "expected_profit": results.get("total_pnl_pct", 0),
                    "win_rate": results.get("win_rate", 0),
                    "max_target_profit": max_target_profit,
                    "metrics": results
                }
                
                logger.info(f"[STRATEGY_ANALYSIS] {engine_name} 엔진 완료: {symbol} - {suitability} ({score:.0f}점)")
            
            except Exception as e:
                logger.error(f"[STRATEGY_ANALYSIS] {engine_name} 엔진 오류: {symbol} - {e}", exc_info=True)
                # 오류 발생 시 기본값 설정
                engine_results[engine_name.lower()] = {
                    "suitability": "부적합",
                    "score": 0,
                    "expected_profit": 0,
                    "win_rate": 0,
                    "max_target_profit": 0,
                    "metrics": {}
                }
        
        # 5. 가장 적합한 엔진 선택
        best_engine = max(
            engine_results.items(),
            key=lambda x: x[1]["score"]
        )[0].capitalize()
        
        # 6. 최대 목표 수익률% 계산 (변동성 기반)
        max_target_profit = {
            "alpha": calculate_max_target_profit("Alpha", volatility, engine_results.get("alpha", {}).get("metrics", {})),
            "beta": calculate_max_target_profit("Beta", volatility, engine_results.get("beta", {}).get("metrics", {})),
            "gamma": calculate_max_target_profit("Gamma", volatility, engine_results.get("gamma", {}).get("metrics", {}))
        }
        
        # 7. 리스크 관리 정보
        risk_management = {
            "stop_loss": 0.5,      # 손절 0.5% (모든 엔진 공통)
            "trailing_stop": 0.3   # 트레일링 스톱 0.3% (모든 엔진 공통)
        }
        
        logger.info(f"[STRATEGY_ANALYSIS] 완료: {symbol} - 추천 엔진: {best_engine}")
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "best_engine": best_engine,
                "volatility": volatility,
                "max_target_profit": max_target_profit,
                "risk_management": risk_management,
                "engine_results": engine_results
            }
        }
    
    except Exception as e:
        logger.error(f"❌ [STRATEGY_ANALYSIS ERROR] {symbol}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

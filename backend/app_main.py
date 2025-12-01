import asyncio
import os
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- 경로 설정 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# --- 모듈 임포트 ---
from backend.core.yona_service import YonaService
from backend.core.engine_manager import get_engine_manager
from backend.api.routes import router as api_router
from backend.api.ws_manager import ws_manager
from backend.utils.logger import setup_logger


def create_app() -> FastAPI:
    """FastAPI 애플리케이션을 생성하고 설정합니다."""
    app = FastAPI(title="YONA Vanguard Futures (new) - Backend")

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 로거 설정
    logger = setup_logger()

    # .env 파일 로드
    dotenv_path = os.path.join(ROOT_DIR, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        logger.info(f".env 파일 로드 완료: {dotenv_path}")

    # 핵심 서비스(YonaService) 초기화
    yona_service = YonaService(logger=logger)
    yona_service.set_broadcaster(ws_manager.broadcast_json)
    app.state.yona_service = yona_service

    # API 라우터 포함
    app.include_router(api_router, prefix="/api/v1")

    @app.on_event("startup")
    async def on_startup():
        """서버 시작 시 실행될 로직"""
        logger.info("YONA Vanguard Futures (new) 백엔드 서버 시작 중...")
        try:
            await app.state.yona_service.initialize()
            app.state.yona_service.run_main_loop()
            logger.info("YonaService 초기화 및 메인 루프 시작 완료.")
            
            # 엔진 매니저 초기화 및 WebSocket 콜백 연결
            # 실현 손익 콜백 설정 (YonaService에 전달)
            def on_realized_pnl(engine_name: str, amount: float):
                """실현 손익 콜백"""
                app.state.yona_service.add_realized_pnl(engine_name, amount)
                # 헤더 업데이트로 Account total balance 및 P&L % 반영
                asyncio.create_task(app.state.yona_service._update_header_data())
            
            from backend.core.engine_manager import EngineManager
            # 엔진 매니저 DB 경로 설정 (YonaService와 동일한 경로)
            db_path = os.path.join(ROOT_DIR, "yona_vanguard.db")
            # 싱글톤 패턴이므로 첫 생성 시 db_path 전달
            engine_manager = get_engine_manager(db_path=db_path)
            engine_manager._realized_pnl_callback = on_realized_pnl
            engine_manager.add_message_callback(ws_manager.broadcast_json)
            logger.info("EngineManager 초기화 및 WebSocket 연결 완료.")
            
        except Exception as e:
            logger.critical(f"서버 시작 중 치명적인 오류 발생: {e}", exc_info=True)

    @app.on_event("shutdown")
    async def on_shutdown():
        """서버 종료 시 실행될 로직"""
        logger.info("YONA Vanguard Futures (new) 백엔드 서버 종료 중...")
        
        # 엔진 매니저 종료
        try:
            engine_manager = get_engine_manager()
            engine_manager.shutdown()
            logger.info("EngineManager 종료 완료.")
        except Exception as e:
            logger.error(f"EngineManager 종료 중 오류: {e}")
        
        await app.state.yona_service.shutdown()
        logger.info("YONA Vanguard Futures (new) 백엔드 서버가 성공적으로 종료되었습니다.")

    # WebSocket 엔드포인트 추가
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text() # 클라이언트로부터 메시지 대기
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", 8200)) # 새로운 앱을 위한 신규 포트
    uvicorn.run(app, host=host, port=port, log_level="info")
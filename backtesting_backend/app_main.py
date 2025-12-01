from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from backtesting_backend.api.backtest_router import router as backtest_router
from backtesting_backend.core.logger import configure_logging, logger
from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.core.config_manager import config
import os
import sys
import traceback
import signal

# imports required for constructing services
from backtesting_backend.api_client import BinanceClient, RateLimitManager
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.database.repositories.backtest_result_repository import BacktestResultRepository
from backtesting_backend.core.data_loader import DataLoader
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator
from backtesting_backend.core.parameter_optimizer import ParameterOptimizer
from backtesting_backend.core.backtest_service import BacktestService

def create_app() -> FastAPI:
	app = FastAPI(title="YONA Vanguard Backtesting Backend")

	# CORS - allow local GUI/dev origins by default (adjust in production)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=["http://localhost", "http://localhost:8080"],
		allow_methods=["*"],
		allow_headers=["*"],
	)

	# Expose backtesting endpoints under the same API namespace the GUI expects
	# (e.g. GET /api/v1/backtest/strategy-analysis)
	app.include_router(backtest_router, prefix="/api/v1/backtest")

	@app.on_event("startup")
	async def startup_event():
		logger.info("Starting Backtesting Backend...")

		# load and validate config
		try:
			config.validate()
		except Exception as e:
			logger.warning("Config validation warning: %s", e)

		# init DB
		await BacktestDB.get_instance().init()

		# attach config to app.state for routers to access
		app.state.config = config

		# instantiate core singletons and services and attach to app.state
		rate_limiter = RateLimitManager()
		binance_client = BinanceClient(api_key=getattr(config, 'BINANCE_API_KEY', None), api_secret=getattr(config, 'BINANCE_SECRET_KEY', None), rate_limit_manager=rate_limiter)

		kline_repo = KlineRepository()
		result_repo = BacktestResultRepository()

		data_loader = DataLoader(binance_client=binance_client, kline_repo=kline_repo)
		analyzer = StrategyAnalyzer()
		simulator = StrategySimulator(analyzer)
		optimizer = ParameterOptimizer(simulator)

		backtest_service = BacktestService(data_loader=data_loader, simulator=simulator, optimizer=optimizer, result_repo=result_repo)

		app.state.rate_limiter = rate_limiter
		app.state.binance_client = binance_client
		app.state.kline_repo = kline_repo
		app.state.result_repo = result_repo
		app.state.data_loader = data_loader
		app.state.analyzer = analyzer
		app.state.simulator = simulator
		app.state.optimizer = optimizer
		app.state.backtest_service = backtest_service

		logger.info("Backtesting Backend started")

		# Log process information for diagnostics
		try:
			pid = os.getpid()
			ppid = os.getppid()
			logger.info("Process info: pid=%s ppid=%s", pid, ppid)
		except Exception:
			logger.exception("Failed to get process info")

		# Install asyncio exception handler to capture unhandled task exceptions
		try:
			loop = asyncio.get_running_loop()

			def _async_exc_handler(loop, context):
				try:
					logger.error("Unhandled async exception: %s", context)
					exc = context.get("exception")
					if exc is not None:
						logger.exception("Exception object:", exc_info=exc)
				except Exception:
					logger.exception("Error in async exception handler")

			loop.set_exception_handler(_async_exc_handler)

			# Install sys.excepthook for uncaught exceptions in main thread
			def _excepthook(exc_type, exc, tb):
				logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))

			sys.excepthook = _excepthook

			# Heartbeat task to show process is alive; helps detect external kills
			async def _heartbeat():
				try:
					while True:
						logger.info("heartbeat: pid=%s alive", os.getpid())
						await asyncio.sleep(10)
				except asyncio.CancelledError:
					logger.info("heartbeat cancelled")

			app.state._heartbeat_task = asyncio.create_task(_heartbeat())
		except Exception:
			logger.exception("Failed to install diagnostic handlers")

	@app.on_event("shutdown")
	async def shutdown_event():
		logger.info("Shutting down Backtesting Backend...")
		# close clients and DB
		bc = getattr(app.state, "binance_client", None)
		if bc:
			try:
				await bc.close()
			except Exception:
				logger.exception("Failed to close Binance client")

		# Cancel heartbeat if present
		hb = getattr(app.state, "_heartbeat_task", None)
		if hb:
			hb.cancel()
			try:
				await hb
			except Exception:
				# ignore cancellation exceptions
				pass

		await BacktestDB.get_instance().close()
		logger.info("Shutdown complete")

	return app

app = create_app()

if __name__ == "__main__":
	import uvicorn

	# Bind to 0.0.0.0 and default to port 8001 so the backtesting service
	# runs on a dedicated port that does not conflict with the main backend (8200).
	uvicorn.run("backtesting_backend.app_main:app", host="0.0.0.0", port=8001, reload=True)

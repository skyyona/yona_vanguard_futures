import os
from dotenv import load_dotenv
from backend.utils.logger import setup_logger

logger = setup_logger()

def get_config(key: str, default: str = None) -> str:
    """환경 변수 또는 .env 파일에서 설정 값을 가져옵니다."""
    value = os.getenv(key, default)
    return value

# .env 파일 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f".env 파일 로드 완료: {env_path}")
else:
    logger.warning(f".env 파일을 찾을 수 없습니다: {env_path}")

# Binance API 설정 (.env에서 직접 로드)
BINANCE_API_KEY = get_config("BINANCE_API_KEY")
BINANCE_SECRET_KEY = get_config("BINANCE_SECRET_KEY")
BINANCE_BASE_URL = get_config("BINANCE_BASE_URL", "https://fapi.binance.com")
BINANCE_WS_BASE_URL_PUBLIC = get_config("BINANCE_WS_BASE_URL_PUBLIC", "wss://fstream.binance.com/ws")
BINANCE_WS_BASE_URL_USER = get_config("BINANCE_WS_BASE_URL_USER", "wss://fstream.binance.com/ws")

# API 키 검증
if BINANCE_API_KEY and BINANCE_SECRET_KEY:
    logger.info("Binance API 키 로드 성공")
else:
    logger.warning("Binance API 키/시크릿 로드 실패. .env 파일을 확인하세요.")



import os
from dotenv import load_dotenv
from backend.utils.logger import setup_logger

logger = setup_logger()


def get_config(key: str, default: str = None) -> str:
    """환경 변수 또는 .env 파일에서 설정 값을 가져옵니다."""
    value = os.getenv(key, default)
    return value


def _get_bool(key: str, default: str = "false") -> bool:
    """부울 환경 변수를 안전하게 파싱합니다."""
    return str(get_config(key, default)).lower() in ("1", "true", "yes", "y")


def _get_int(key: str, default: str) -> int:
    """정수 환경 변수를 안전하게 파싱합니다."""
    raw = get_config(key, default)
    try:
        return int(raw)
    except Exception:
        logger.warning("정수 환경 변수 %s 값 '%s' 이(가) 올바르지 않아 기본값 %s 을(를) 사용합니다.", key, raw, default)
        return int(default)


def _get_float(key: str, default: str) -> float:
    """실수 환경 변수를 안전하게 파싱합니다."""
    raw = get_config(key, default)
    try:
        return float(raw)
    except Exception:
        logger.warning("실수 환경 변수 %s 값 '%s' 이(가) 올바르지 않아 기본값 %s 을(를) 사용합니다.", key, raw, default)
        return float(default)


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

# Engine Executor forwarding flags (Live Backend -> Engine Backend)
ENABLE_ENGINE_EXECUTOR = str(get_config("ENABLE_ENGINE_EXECUTOR", "false")).lower() in ("1", "true", "yes")
ENGINE_EXECUTOR_URL = get_config("ENGINE_EXECUTOR_URL", "")
ENGINE_EXECUTOR_TOKEN = get_config("ENGINE_EXECUTOR_TOKEN", "")

if ENABLE_ENGINE_EXECUTOR:
    logger.info(f"Engine executor forwarding ENABLED -> {ENGINE_EXECUTOR_URL}")
else:
    logger.info("Engine executor forwarding DISABLED")

# Redis broker for Engine Backend (producer/consumer)
ENGINE_BROKER_ENABLED = str(get_config("ENGINE_BROKER_ENABLED", "false")).lower() in ("1", "true", "yes")
ENGINE_BROKER_URL = get_config("ENGINE_BROKER_URL", "redis://localhost:6379/0")
ENGINE_BROKER_STREAM = get_config("ENGINE_BROKER_STREAM", "orders_stream")

if ENGINE_BROKER_ENABLED:
    logger.info(f"Engine broker enabled -> {ENGINE_BROKER_URL} stream={ENGINE_BROKER_STREAM}")
else:
    logger.info("Engine broker disabled")

# 트레이딩 모드 및 리스크 한도 설정 (공통 플래그)

# 선물 테스트넷 사용 여부 (기본값: false)
BINANCE_USE_TESTNET = _get_bool("BINANCE_USE_TESTNET", "false")

# 실거래 활성화 여부
# 사용자의 의도: 기본적으로는 모든 전략 주문이 실제로 실행될 수 있도록 하고,
# 필요할 때만 사용자가 명시적으로 끄는 스위치로 사용
LIVE_TRADING_ENABLED = _get_bool("LIVE_TRADING_ENABLED", "true")

# 리스크 한도
# 사용자의 의도: 레버리지/포지션 크기는 사용자가 전략/엔진에서 직접 결정하며,
# 여기의 값은 원할 때만 선택적으로 제한을 둘 수 있는 옵션으로만 사용한다.
# 따라서 기본값은 "제한 없음"(0 또는 음수는 제한 미적용)으로 둔다.
MAX_LEVERAGE = _get_int("MAX_LEVERAGE", "0")
MAX_POSITION_USDT = _get_float("MAX_POSITION_USDT", "0")
DAILY_MAX_LOSS_USDT = _get_float("DAILY_MAX_LOSS_USDT", "0")

logger.info(
    "Trading safety config -> testnet=%s live_trading=%s max_leverage=%s max_position_usdt=%s daily_max_loss_usdt=%s",
    BINANCE_USE_TESTNET,
    LIVE_TRADING_ENABLED,
    MAX_LEVERAGE,
    MAX_POSITION_USDT,
    DAILY_MAX_LOSS_USDT,
)



"""로깅 유틸리티 - 파일 기반 전략 로깅"""
import logging
import os
from datetime import datetime
from pathlib import Path


def setup_strategy_logger(
    name: str,
    log_dir: str = "logs/strategy",
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    전략 전용 로거 설정
    
    Args:
        name: 로거 이름 (예: "NewModular")
        log_dir: 로그 파일 저장 디렉터리
        level: 로깅 레벨
    
    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 로그 디렉터리 생성
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 파일 핸들러 - 일반 로그
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_path / f"{name}_{today}.log"
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    
    # 파일 핸들러 - 거래 이벤트 전용
    trade_log_file = log_path / f"{name}_trades_{today}.log"
    trade_handler = logging.FileHandler(trade_log_file, encoding="utf-8")
    trade_handler.setLevel(logging.INFO)
    trade_handler.addFilter(TradeEventFilter())
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    trade_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    trade_handler.setFormatter(trade_formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(trade_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"로거 초기화 완료: {name}")
    logger.debug(f"로그 파일: {log_file}")
    logger.debug(f"거래 로그: {trade_log_file}")
    
    return logger


class TradeEventFilter(logging.Filter):
    """거래 이벤트만 필터링"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # 메시지에 특정 키워드 포함 시만 기록
        keywords = ["진입", "청산", "ENTRY", "EXIT", "주문", "ORDER"]
        return any(kw in record.getMessage() for kw in keywords)


def log_trade_event(logger: logging.Logger, event_type: str, symbol: str, **kwargs):
    """
    거래 이벤트 로깅 (표준화된 형식)
    
    Args:
        logger: Logger 인스턴스
        event_type: "ENTRY" | "EXIT" | "ENTRY_FAIL" | "EXIT_FAIL"
        symbol: 심볼
        **kwargs: 추가 정보 (price, quantity, pnl, reason 등)
    """
    msg_parts = [f"[{event_type}] {symbol}"]
    
    if "price" in kwargs:
        msg_parts.append(f"가격={kwargs['price']:.4f}")
    if "quantity" in kwargs:
        msg_parts.append(f"수량={kwargs['quantity']:.6f}")
    if "pnl" in kwargs:
        msg_parts.append(f"PNL={kwargs['pnl']:.2f} USDT")
    if "reason" in kwargs:
        msg_parts.append(f"이유={kwargs['reason']}")
    if "order_id" in kwargs:
        msg_parts.append(f"주문ID={kwargs['order_id']}")
    
    logger.info(" | ".join(msg_parts))


def log_risk_event(logger: logging.Logger, event: str, position, **kwargs):
    """
    리스크 관리 이벤트 로깅
    
    Args:
        logger: Logger 인스턴스
        event: 이벤트 설명 (예: "트레일링 스톱 업데이트")
        position: PositionState 인스턴스
        **kwargs: 추가 정보
    """
    msg = f"[RISK] {event} | {position.symbol} @ {position.entry_price:.2f}"
    
    if "stop_loss" in kwargs:
        msg += f" | 손절={kwargs['stop_loss']:.2f}"
    if "take_profit" in kwargs:
        msg += f" | 익절={kwargs['take_profit']:.2f}"
    if "trailing_activated" in kwargs:
        msg += f" | 트레일링={'ON' if kwargs['trailing_activated'] else 'OFF'}"
    
    logger.debug(msg)


def log_signal_event(logger: logging.Logger, signal):
    """
    신호 생성 이벤트 로깅
    
    Args:
        logger: Logger 인스턴스
        signal: SignalResult 인스턴스
    """
    logger.debug(
        f"[SIGNAL] {signal.action.value} | 점수={signal.score:.1f}/170 "
        f"| 신뢰도={signal.confidence_pct:.1f}% | 트리거={', '.join(signal.triggers[:3])}"
    )

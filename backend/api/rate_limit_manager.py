import time
import threading
from backend.utils.logger import setup_logger

logger = setup_logger()

class RateLimitManager:
    """바이낸스 API Rate Limit 관리"""
    
    def __init__(self):
        self._lock = threading.Lock()
        # Weight 기반 Rate Limit
        self._weight_limits = {
            "general": {"limit": 2400, "window": 60},  # 60초당 2400 Weight
            "orders": {"limit": 300, "window": 10},    # 10초당 300 Weight
        }
        self._weight_counts = {category: [] for category in self._weight_limits}
    
    def wait_for_permission(self, category: str = "general", weight: int = 1):
        """Rate Limit을 확인하고 필요시 대기합니다."""
        with self._lock:
            now = time.time()
            limit_info = self._weight_limits.get(category, self._weight_limits["general"])
            weight_list = self._weight_counts[category]
            
            # 오래된 기록 제거
            window_start = now - limit_info["window"]
            self._weight_counts[category] = [w for w in weight_list if w > window_start]
            
            # 현재 Weight 합계 계산
            current_weight = sum(1 for _ in self._weight_counts[category])
            
            # Limit 초과 시 대기
            if current_weight + weight > limit_info["limit"]:
                if weight_list:
                    sleep_time = weight_list[0] + limit_info["window"] - now + 0.1
                    if sleep_time > 0:
                        logger.debug(f"Rate Limit 대기: {sleep_time:.2f}초")
                        time.sleep(sleep_time)
                        # 다시 오래된 기록 제거
                        now = time.time()
                        window_start = now - limit_info["window"]
                        self._weight_counts[category] = [w for w in self._weight_counts[category] if w > window_start]
            
            # Weight 기록 추가
            for _ in range(weight):
                self._weight_counts[category].append(now)

# 전역 인스턴스
rate_limit_manager = RateLimitManager()



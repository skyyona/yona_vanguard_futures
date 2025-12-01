from datetime import datetime, timezone, timedelta
from backend.utils.logger import setup_logger

logger = setup_logger()

class SessionManager:
    """글로벌 세션 관리 클래스"""
    
    @staticmethod
    def get_global_session() -> str:
        """현재 시간의 글로벌 세션 정보를 반환합니다."""
        try:
            # KST 시간 계산 (UTC+9)
            utc_now = datetime.now(timezone.utc)
            kst = utc_now.astimezone(timezone(timedelta(hours=9)))
            hour = kst.hour
            
            # 세션 판단 (사용자 정의 로직과 동일)
            if 21 <= hour or hour < 1:
                return "런던-뉴욕 겹침 (거래량 최대)"
            elif 16 <= hour < 18:
                return "도쿄-런던 겹침 (아시아 마감)"
            elif 9 <= hour < 16:
                return "시드니-도쿄 겹침 (아시아 활성)"
            elif 7 <= hour < 9:
                return "시드니 세션"
            elif 18 <= hour < 21:
                return "런던 세션 (유럽 활성)"
            elif 1 <= hour < 6:
                return "뉴욕 세션 (미주 활성)"
            else:
                return "시장휴무"
        except Exception as e:
            logger.error(f"글로벌 세션 계산 중 오류 발생: {e}", exc_info=True)
            return "세션 계산 중"



# app/utils/session_helpers.py
import logging

logger = logging.getLogger(__name__)


def session_exists(session_repo, session_id: str) -> bool:
    """
    sessions 테이블에 해당 session_id가 아직 존재하는지 확인.
    - 사용자가 생성 도중 삭제했을 때 에러 방지용
    
    Args:
        session_repo: SessionRepo 인스턴스 (Postgres or Memory)
        session_id: 확인할 세션 ID
        
    Returns:
        bool: 세션이 존재하면 True, 없으면 False
    """
    try:
        session = session_repo.get_session(session_id)
        return session is not None
    except Exception as e:
        logger.error(f"[session_exists] 확인 실패 (session_id={session_id}): {e}")
        return False


def to_seconds(time_str):
    """타임스탬프 파싱 -> 초로 바꾸기"""
    if time_str is None:
        return None
    if isinstance(time_str, (int, float)):
        return float(time_str)

    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        return float(time_str)

    return int(h) * 3600 + int(m) * 60 + float(s)
# app/utils/session_helpers.py
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

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


def to_iso_z(dt: datetime) -> str:
    """datetime -> ISO 8601 (UTC, Z suffix)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def unwrap_response_tuple(response: Any, result: Tuple[Dict[str, Any], int]) -> Dict[str, Any]:
    """(body, status_code) 튜플을 FastAPI Response에 반영하고 body만 반환."""
    body, status_code = result
    try:
        response.status_code = int(status_code)
    except Exception:
        response.status_code = 500
    return body


# 프론트에 노출할 current_step & progress (진행형 단계)
PUBLIC_STEP_PROGRESS = {
    "uploading": 5, # 파일 업로드/등록 중
    "converting": 10, # 업로드 완료, 변환/큐 등록 중
    "extracting": 25, # 텍스트 추출 진행 중
    "postprocessing": 35, # 메타데이터 생성 및 텍스트 병합
    "writing_script": 60, # 스크립트 생성
    "generating_audio": 80, # 오디오 생성
    "finalizing": 90, # 오디오 병합 및 트랜스크립트 생성 + 정리/업로드
    "completed": 100, # 생성 완료
    "error": -1, # 오류
}

# 내부(raw) step -> 공개(public) step alias
_STEP_ALIASES = {
    # 업로드/초기
    "start": "uploading",
    "파일 업로드 시작": "uploading",
    "파일 업로드 완료 및 변환 시작": "converting",

    # graph.py / legacy 완료 마커 흡수
    "complete": "completed",
    "completed": "completed",
    "error": "error",

    # queue/function_app 세분화 단계 흡수
    "extract_texts": "extracting",
    "extract_ocr": "extracting",
    "extract_ocr_complete": "extracting",
    "extract_complete": "postprocessing",
    "combine_texts": "postprocessing",
    "combine_complete": "postprocessing",
    "extract_finalize": "postprocessing",

    "generate_script": "writing_script",
    "script": "writing_script",
    "script_complete": "writing_script",

    "generate_audio": "generating_audio",
    "audio": "generating_audio",
    "audio_complete": "generating_audio",

    "merge_audio": "finalizing",
    "merge_complete": "finalizing",
    "finalize": "finalizing",
}


def normalize_current_step(raw_step: Any, status: Any = None) -> str:
    """DB raw current_step을 프론트 공개 단계로 정규화."""
    step = (raw_step or "").strip() if isinstance(raw_step, str) else ""
    st = (status or "").strip() if isinstance(status, str) else ""

    # status 기반 보정
    if st == "completed":
        return "completed"
    if st in ("failed", "error"):
        return "error"

    if not step:
        return "uploading"

    if step in _STEP_ALIASES:
        return _STEP_ALIASES[step]

    # 새 raw step이 추가돼도 맞는 단계로 되게 처리
    low = step.lower()
    if "upload" in low:
        return "uploading"
    if "convert" in low:
        return "converting"
    if "extract" in low or "ocr" in low:
        return "extracting"
    if "combine" in low or "finalize" in low:
        return "postprocessing"
    if "script" in low:
        return "writing_script"
    if "audio" in low or "tts" in low:
        return "generating_audio"
    if "merge" in low:
        return "finalizing"

    return "uploading"


def get_public_progress(raw_step: Any, status: Any = None) -> int:
    step = normalize_current_step(raw_step, status=status)
    return int(PUBLIC_STEP_PROGRESS.get(step, 0))

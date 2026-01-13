from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import timezone

from state import create_channel, get_channel, delete_channel #, list_sessions, delete_session
from utils.response import success_response, error_response
from utils.error_codes import ErrorCodes

router = APIRouter(prefix="/v1/channels", tags=["channels"])

# 채널 생성
@router.post("", status_code=201)
def create_channel_api():
    try:
        ch = create_channel()
        # ISO8601 + Z
        created_at = ch.created_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

        body, code = success_response(
            data={"channel_id": ch.channel_id, "created_at": created_at},
            status_code=201
        )
        return JSONResponse(content=body, status_code=code)

    except Exception:
        body, code = error_response(
            message="Internal server error",
            error_code=ErrorCodes.INTERNAL_ERROR,
            status_code=500
        )
        return JSONResponse(content=body, status_code=code)

# 채널 삭제
@router.delete("/{channel_id}")
def delete_channel_api(channel_id: str):
    try:
        ch = get_channel(channel_id)
        if not ch:
            body, code = error_response(
                message="Channel not found",
                error_code=ErrorCodes.CHANNEL_NOT_FOUND,
                status_code=404
            )
            return JSONResponse(content=body, status_code=code)

        # (권장) 채널에 딸린 세션 정리
        # TODO: 세션/파일 정리는 세션 담당 파트(EST-319)에서 합치기
        # for s in list_sessions(channel_id=channel_id):
        #     delete_session(s.session_id)

        delete_channel(channel_id)

        body, code = success_response(
            data=None,
            message="Channel deleted",
            status_code=200
        )
        return JSONResponse(content=body, status_code=code)

    except Exception:
        body, code = error_response(
            message="Internal server error",
            error_code=ErrorCodes.INTERNAL_ERROR,
            status_code=500
        )
        return JSONResponse(content=body, status_code=code)

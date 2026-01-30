# app/routers/channels.py
from fastapi import APIRouter, Depends, Response

from app.dependencies.repos import get_channel_repo, get_session_repo
from app.services.storage_service import get_storage
from app.utils.response import success_response, error_response
from app.utils.error_codes import ErrorCodes
from app.utils.session_helpers import unwrap_response_tuple, to_iso_z

router = APIRouter(prefix="/v1/channels", tags=["channels"])


@router.post("")
def create_channel_api(
    response: Response,
    channel_repo=Depends(get_channel_repo),
):
    """채널 생성"""
    try:
        ch = channel_repo.create_channel()
        created_at = to_iso_z(ch["created_at"])

        return unwrap_response_tuple(
            response,
            success_response(
                data={"channel_id": ch["channel_id"], "created_at": created_at},
                status_code=201,
            ),
        )

    except Exception as e:
        print(f"[create_channel_api] error: {e}")
        return unwrap_response_tuple(
            response,
            error_response(
                message="Internal server error",
                error_code=ErrorCodes.INTERNAL_ERROR,
                status_code=500,
            ),
        )


@router.delete("/{channel_id}")
def delete_channel_api(
    channel_id: str,
    response: Response,
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
    storage=Depends(get_storage),
):
    """채널 삭제"""
    try:
        ch = channel_repo.get_channel(channel_id)
        if not ch:
            return unwrap_response_tuple(
                response,
                error_response(
                    message="Channel not found",
                    error_code=ErrorCodes.CHANNEL_NOT_FOUND,
                    status_code=404,
                ),
            )

        # 세션들의 파일 정리
        sessions = session_repo.list_sessions_by_channel(channel_id)
        for sess in sessions:
            storage_prefix = sess.get("storage_prefix")
            if storage_prefix and hasattr(storage, "delete_prefix"):
                try:
                    storage.delete_prefix(storage_prefix)
                except Exception as e:
                    print(f"Storage 삭제 실패 (무시): {storage_prefix}, {e}")

        # 세션 삭제
        session_repo.delete_sessions_by_channel(channel_id)

        # 채널 삭제
        channel_repo.delete_channel(channel_id)

        return unwrap_response_tuple(
            response,
            success_response(
                data=None,
                message="Channel deleted",
                status_code=200,
            ),
        )

    except Exception as e:
        print(f"채널 삭제 오류: {e}")
        return unwrap_response_tuple(
            response,
            error_response(
                message="Internal server error",
                error_code=ErrorCodes.INTERNAL_ERROR,
                status_code=500,
            ),
        )
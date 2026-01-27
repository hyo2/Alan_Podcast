import io
import re
from fastapi import APIRouter, Path, Depends, Request
from fastapi.responses import StreamingResponse

from app.dependencies.repos import get_channel_repo, get_session_repo
from app.services.storage_service import get_storage
from app.utils.response import error_response
from app.utils.error_codes import ErrorCodes


router = APIRouter(prefix="/v1/channels/{channel_id}/files", tags=["streaming"])

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get("/audio/{session_id}/{chapter}")
async def stream_audio(
    request: Request,
    channel_id: str = Path(..., description="채널 ID"),
    session_id: str = Path(..., description="세션 ID"),
    chapter: int = Path(..., description="챕터 번호"),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
    storage=Depends(get_storage),
):
    """오디오 스트리밍 API"""

    # 1. 챕터는 1만 허용
    if chapter != 1:
        return error_response(
            message="챕터를 찾을 수 없습니다.",
            error_code=ErrorCodes.NOT_FOUND,
            status_code=404,
        )

    # 2. 채널 확인
    ch = channel_repo.get_channel(channel_id)
    if not ch:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404,
        )

    # 3. 세션 확인
    session = session_repo.get_session(session_id)
    if not session or session["channel_id"] != channel_id:
        return error_response(
            message="요청하신 세션을 찾을 수 없습니다.",
            error_code=ErrorCodes.SESSION_NOT_FOUND,
            status_code=404,
        )

    # 4. 상태 확인 (completed만 허용)
    if session["status"] != "completed":
        return error_response(
            message="처리가 완료되지 않았습니다.",
            error_code=ErrorCodes.PROCESSING_FAILED,
            status_code=400,
        )

    # 5. audio_key 확인
    audio_key = session.get("audio_key")
    if not audio_key:
        return error_response(
            message="오디오 파일을 찾을 수 없습니다.",
            error_code=ErrorCodes.NOT_FOUND,
            status_code=404,
        )

    try:
        range_header = request.headers.get("range")

        # Range 요청이면: 전체크기만 먼저 조회 + 필요한 바이트만 다운로드
        if range_header:
            m = _RANGE_RE.match(range_header.strip())
            if m:
                start_s, end_s = m.groups()

                total = storage.get_size(audio_key)

                if start_s == "" and end_s != "":
                    # suffix range: bytes=-N (마지막 N바이트)
                    length = int(end_s)
                    start = max(total - length, 0)
                    end = total - 1
                else:
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else total - 1

                start = max(start, 0)
                end = min(end, total - 1)

                if start > end:
                    return StreamingResponse(
                        io.BytesIO(b""),
                        status_code=416,
                        headers={"Content-Range": f"bytes */{total}"},
                    )

                chunk = storage.download_range(audio_key, start, end)

                headers = {
                    "Content-Type": "audio/mpeg",
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Content-Length": str(len(chunk)),
                }
                return StreamingResponse(io.BytesIO(chunk), status_code=206, headers=headers)

        # Range 없으면 전체 다운로드
        file_data = storage.download(audio_key)
        total = len(file_data)
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="audio/mpeg",
            headers={
                "Content-Length": str(total),
                "Accept-Ranges": "bytes",
            },
        )

    except Exception as e:
        print(f"오디오 스트리밍 실패: {e}")
        return error_response(
            message="파일 읽기 실패",
            error_code=ErrorCodes.INTERNAL_ERROR,
            status_code=500,
        )

import io
import re
from fastapi import APIRouter, Path, Depends, Request, Response
from fastapi.responses import StreamingResponse

from app.dependencies.repos import get_channel_repo, get_session_repo
from app.dependencies.auth import require_access
from app.services.storage_service import get_storage
from app.utils.response import error_response
from app.utils.error_codes import ErrorCodes
from app.utils.session_helpers import unwrap_response_tuple

router = APIRouter(prefix="/v1/channels/{channel_id}/files", tags=["streaming"], dependencies=[Depends(require_access)],)

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get("/audio/{session_id}/{chapter}")
async def stream_audio(
    request: Request,
    response: Response,
    channel_id: str = Path(..., description="채널 ID"),
    session_id: str = Path(..., description="세션 ID"),
    chapter: int = Path(..., description="챕터 번호"),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
    storage=Depends(get_storage),
):
    """오디오 스트리밍 API

    - Range 헤더가 있으면 206 Partial Content로 부분 바이트 응답
    - Range 헤더가 없으면 200 OK로 전체 응답
    - 에러 응답은 (dict, status_code) 튜플 스펙을 유지하면서도 실제 HTTP status가 맞게 내려가도록
      Response.status_code를 세팅한 뒤 dict만 반환한다.
    """

    # 1) 챕터는 1만 허용
    if chapter != 1:
        return unwrap_response_tuple(
            response,
            error_response(
                message="챕터를 찾을 수 없습니다.",
                error_code=ErrorCodes.NOT_FOUND,
                status_code=404,
            ),
        )

    # 2) 채널 확인
    ch = channel_repo.get_channel(channel_id)
    if not ch:
        return unwrap_response_tuple(
            response,
            error_response(
                message="요청하신 채널을 찾을 수 없습니다.",
                error_code=ErrorCodes.CHANNEL_NOT_FOUND,
                status_code=404,
            ),
        )

    # 3) 세션 확인
    session = session_repo.get_session(session_id)
    if not session or session.get("channel_id") != channel_id:
        return unwrap_response_tuple(
            response,
            error_response(
                message="요청하신 세션을 찾을 수 없습니다.",
                error_code=ErrorCodes.SESSION_NOT_FOUND,
                status_code=404,
            ),
        )

    # 4) 상태 확인 (completed만 스트리밍 허용)
    if session.get("status") != "completed":
        # 처리 미완료/실패 모두 400 PROCESSING_FAILED
        return unwrap_response_tuple(
            response,
            error_response(
                message="처리가 완료되지 않았습니다.",
                error_code=ErrorCodes.PROCESSING_FAILED,
                status_code=400,
            ),
        )

    # 5) audio_key 확인
    audio_key = session.get("audio_key")
    if not audio_key:
        # completed로 표시됐는데 결과가 없으면 서버 상태 불일치로 판단
        return unwrap_response_tuple(
            response,
            error_response(
                message="완료된 세션의 오디오 파일 정보를 찾을 수 없습니다.",
                error_code=ErrorCodes.INTERNAL_ERROR,
                status_code=500,
            ),
        )

    try:
        range_header = request.headers.get("range")

        # Range 요청이면: 전체크기 조회 + 필요한 바이트만 다운로드
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
                        media_type="audio/mpeg",
                    )

                chunk = storage.download_range(audio_key, start, end)

                headers = {
                    "Content-Type": "audio/mpeg",
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Content-Length": str(len(chunk)),
                }
                return StreamingResponse(
                    io.BytesIO(chunk),
                    status_code=206,
                    headers=headers,
                    media_type="audio/mpeg",
                )

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
        return unwrap_response_tuple(
            response,
            error_response(
                message="파일 읽기 실패",
                error_code=ErrorCodes.INTERNAL_ERROR,
                status_code=500,
            ),
        )
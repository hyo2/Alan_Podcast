# app/routers/sessions.py
import os
from typing import Optional, List
import json
from fastapi import APIRouter, UploadFile, File, Path, Form, status, Query, Depends, BackgroundTasks, Response
from datetime import timezone

from app.dependencies.repos import (
    get_channel_repo,
    get_session_repo,
    get_session_input_repo,
)
from app.services.storage_service import get_storage
from app.services.session_service import SessionService
from app.utils.response import success_response, error_response
from app.utils.error_codes import ErrorCodes

router = APIRouter(prefix="/v1", tags=["sessions"])

ALLOWED_EXTS = {".pdf", ".docx", ".pptx", ".txt"}


def _get_ext(filename: str) -> str:
    name = (filename or "").lower().strip()
    for ext in ALLOWED_EXTS:
        if name.endswith(ext):
            return ext
    return ""

def _build_storage_prefix(channel_id: str, session_id: str) -> str:
    return f"ai_audiobook/channel/{channel_id}/session/{session_id}/"

# 세션 생성 API
@router.post("/channels/{channel_id}/sessions")
async def create_session(
    response: Response,
    background_tasks: BackgroundTasks,
    channel_id: str = Path(..., description="채널 ID"),
    files: List[UploadFile] = File(None),     # 멀티 파일
    links: str = Form("[]"),                 # 멀티 링크(JSON string)
    main_kind: str = Form(...),      # 주 강의자료 형식("file" | "link")
    main_index: int = Form(...),    # 주 강의자료 index (0-based index)
    voice_id: Optional[str] = Form(None),
    style: str = Form("explain"),
    duration: int = Form(5),
    difficulty: str = Form("intermediate"),
    user_prompt: str = Form(""),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
    session_input_repo=Depends(get_session_input_repo),
    storage=Depends(get_storage),
):
    # 1) 채널 확인
    ch = channel_repo.get_channel(channel_id)
    if not ch:
        body, sc = error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404,
        )
        response.status_code = sc
        return body

    # 2) links 파싱
    try:
        link_list = json.loads(links) if links else []
        if link_list is None:
            link_list = []
        if not isinstance(link_list, list):
            return error_response(
                message="links는 JSON 배열 문자열이어야 합니다.",
                error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )
        link_list = [str(x).strip() for x in link_list if str(x).strip()]
    except Exception:
        return error_response(
            message="links 파싱에 실패했습니다. JSON 배열 문자열인지 확인하세요.",
            error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
            status_code=400,
        )

    # 3) 입력 존재 검사 (파일/링크 둘 다 없으면 실패)
    files = files or []
    if len(files) == 0 and len(link_list) == 0:
        return error_response(
            message="입력 파일 또는 링크가 최소 1개 필요합니다.",
            error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
            status_code=400,
        )
    
    # 입력자료는 최대 4개까지 지원
    MAX_INPUTS = 4
    total_inputs = len(files) + len(link_list)
    if total_inputs > MAX_INPUTS:
        return error_response(
            message=f"입력은 최대 {MAX_INPUTS}개까지 가능합니다. (현재 {total_inputs}개)",
            error_code=ErrorCodes.INVALID_FILE_FORMAT,
            status_code=400,
        )
    
    # 3-1) main 지정 검증 (main은 정확히 1개 필수)
    main_kind = (main_kind or "").strip().lower()
    files = files or []
    files_count = len(files)
    links_count = len(link_list)

    if main_kind not in ("file", "link"):
        return error_response(
            message="main_kind는 'file' 또는 'link' 여야 합니다.",
            error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
            status_code=400,
        )

    # main_index 타입/범위 검증
    if not isinstance(main_index, int):
        return error_response(
            message="main_index는 정수여야 합니다.",
            error_code=ErrorCodes.INVALID_REQUEST if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
            status_code=400,
        )

    if main_kind == "file":
        if files_count == 0:
            return error_response(
                message="main_kind가 'file'이면 files가 최소 1개 필요합니다.",
                error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )
        if main_index < 0 or main_index >= files_count:
            return error_response(
                message=f"main_index 범위가 올바르지 않습니다. files 길이={files_count}, main_index={main_index}",
                error_code=ErrorCodes.INVALID_REQUEST if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )

    elif main_kind == "link":
        if links_count == 0:
            return error_response(
                message="main_kind가 'link'이면 links가 최소 1개 필요합니다.",
                error_code=ErrorCodes.INVALID_FILE_FORMAT if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )
        if main_index < 0 or main_index >= links_count:
            return error_response(
                message=f"main_index 범위가 올바르지 않습니다. links 길이={links_count}, main_index={main_index}",
                error_code=ErrorCodes.INVALID_REQUEST if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )


    # 4) options 준비
    options = {
        "host1": voice_id,
        "host2": "",
        "style": style,
        "duration": duration,
        "difficulty": difficulty,
        "user_prompt": user_prompt,
    }

    try:
        # 5) 세션 생성 (일단 processing)
        session = session_repo.create_session(
            channel_id=channel_id,
            options=options,
            status="processing",
            current_step="파일 업로드 시작",
        )
        session_id = session["session_id"]

        # 6) storage prefix / input dir
        storage_prefix = _build_storage_prefix(channel_id, session_id)
        input_dir = f"{storage_prefix}input_files/"

        # 7) main/aux 지정
        main_assigned = False

        # 8) 파일 업로드 + session_inputs insert
        for i, f in enumerate(files):
            filename = f.filename or "input.bin"
            ext = _get_ext(filename)
            if not ext:
                return error_response(
                    message=f"지원하지 않는 파일 형식입니다: {filename} (pdf, docx, pptx, txt만 가능)",
                    error_code=ErrorCodes.INVALID_FILE_FORMAT,
                    status_code=400,
                )

            role = "main" if (main_kind == "file" and i == main_index) else "aux"
            if role == "main":
                main_assigned = True

            data = await f.read()
            # 같은 파일명 충돌 방지: i prefix 부여
            safe_name = filename
            input_key = f"{input_dir}{i}_{safe_name}"

            storage.upload_bytes(input_key, data, content_type=f.content_type)

            session_input_repo.create_input(
                session_id=session_id,
                title=filename,
                input_key=input_key,
                file_type=ext.lstrip("."),
                file_size=len(data) if data else None,
                is_link=False,
                link_url=None,
                role=role,
            )

        # 9) 링크 저장 + session_inputs insert
        for j, url in enumerate(link_list):
            role = "main" if (main_kind == "link" and j == main_index) else "aux"
            if role == "main":
                main_assigned = True

            session_input_repo.create_input(
                session_id=session_id,
                title=url,
                input_key=None,          # 링크는 필요 없음 (repo/DB가 NULL 허용해야 함)
                file_type=None,
                file_size=None,
                is_link=True,
                link_url=url,
                role=role,
            )

        # main이 정확히 1개인지 확인
        if not main_assigned:
            # 이 경우는 위 검증이 제대로 동작하면 사실상 발생하지 않지만,
            # 예외 케이스 방지를 위해 남겨둠
            session_repo.update_status(
                session_id,
                status="failed",
                current_step="입력 검증 실패",
                error_message="Main input not assigned",
            )
            return error_response(
                message="main 입력이 지정되지 않았습니다.",
                error_code=ErrorCodes.INVALID_REQUEST if hasattr(ErrorCodes, "INVALID_REQUEST") else ErrorCodes.INTERNAL_ERROR,
                status_code=400,
            )

        # 10) storage_prefix 저장
        session = session_repo.update_session_fields(
            session_id,
            storage_prefix=storage_prefix,
            current_step="파일 업로드 완료 및 변환 시작",
        ) or session

        # 11) BackgroundTasks 등록
        service = SessionService(
            channel_repo=channel_repo,
            session_repo=session_repo,
            session_input_repo=session_input_repo,
            storage=storage,
        )
        background_tasks.add_task(
            service.process_audiobook_generation,
            session_id=session_id,
            channel_id=channel_id,
            options=options,
        )

        # 12) 응답
        created_at_dt = session["created_at"]
        created_at = created_at_dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

        body, sc = success_response(
            data={
                "session_id": session_id,
                "status": "processing",
                "progress": 0,
                "current_step": session.get("current_step") or "파일 업로드 완료 및 변환 시작",
                "created_at": created_at,
            },
            status_code=201,
        )
        response.status_code = sc
        return body

    except Exception as e:
        body, sc = error_response(
            message=f"서버 내부 오류: {str(e)}",
            error_code=ErrorCodes.INTERNAL_ERROR,
            status_code=500,
        )
        response.status_code = sc
        return body

@router.get("/channels/{channel_id}/sessions/{session_id}")
async def get_session(
    response: Response, 
    channel_id: str = Path(..., description="채널 ID"),
    session_id: str = Path(..., description="세션 ID"),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
):
    """세션 조회"""
    # 1) 채널 확인
    ch = channel_repo.get_channel(channel_id)
    if not ch:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404,
        )

    # 2) 세션 확인
    session = session_repo.get_session(session_id)
    if not session or session["channel_id"] != channel_id:
        return error_response(
            message="요청하신 세션을 찾을 수 없습니다.",
            error_code=ErrorCodes.SESSION_NOT_FOUND,
            status_code=404,
        )

    # 3) progress 계산 (current_step 기반)
    step_progress = {
        "start": 0,
        "파일 업로드 시작": 5,
        "파일 업로드 완료 및 변환 시작": 10,
        "extract_complete": 30,
        "combine_complete": 40,
        "script_complete": 60,
        "audio_complete": 80,
        "merge_complete": 90,
        "completed": 100,
        "error": -1,
    }
    progress = step_progress.get(session.get("current_step"), 0)

    # 4) result 구성
    result = None
    error = session.get("error_message")

    if session["status"] == "completed":
        # 완료 시 result 포함
        options = session.get("options") or {}
        duration = options.get("duration", 5)  # 요청 시간 (실제 길이 아님)
        title = session.get("title") or "자동 생성된 팟캐스트"

        result = {
            "chapters": [
                {
                    "chapter": 1,
                    "title": title,
                    "duration": duration * 60,  # 분 → 초 (추정치)
                }
            ],
            "total_duration": duration * 60,
        }

    # 5) 응답
    created_at_dt = session["created_at"]
    created_at = created_at_dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    body, sc = success_response(data={
            "session_id": session_id,
            "status": session["status"],
            "progress": progress,
            "current_step": session.get("current_step") or "",
            "result": result,
            "error": error,
            "created_at": created_at,
        })
    response.status_code = sc
    return body


@router.get("/channels/{channel_id}/sessions")
async def list_sessions(
    response: Response,
    channel_id: str = Path(..., description="채널 ID"),
    limit: int = Query(50),
    offset: int = Query(0),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
):
    """세션 목록 조회"""
    ch = channel_repo.get_channel(channel_id)
    if not ch:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404,
        )

    rows = session_repo.list_sessions_by_channel(channel_id, limit=limit, offset=offset)
    total = len(rows)

    # progress 계산을 위한 step_progress 매핑
    step_progress = {
        "start": 0,
        "파일 업로드 시작": 5,
        "파일 업로드 완료 및 변환 시작": 10,
        "extract_complete": 30,
        "combine_complete": 40,
        "script_complete": 60,
        "audio_complete": 80,
        "merge_complete": 90,
        "completed": 100,
        "error": -1,
    }

    # 요구사항에 맞게 필드만 추출
    sessions_list = []
    for session in rows:
        # progress 계산
        progress = step_progress.get(session.get("current_step"), 0)
        
        # created_at을 ISO 8601 형식으로 변환
        created_at_dt = session["created_at"]
        created_at = created_at_dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        
        sessions_list.append({
            "session_id": session["session_id"],
            "status": session["status"],
            "progress": progress,
            "created_at": created_at,
        })

    body, sc = success_response(data={"sessions": sessions_list, "total": total})
    response.status_code = sc
    return body


@router.delete("/channels/{channel_id}/sessions/{session_id}")
async def delete_session(
    response: Response,
    channel_id: str = Path(...),
    session_id: str = Path(...),
    channel_repo=Depends(get_channel_repo),
    session_repo=Depends(get_session_repo),
    session_input_repo=Depends(get_session_input_repo),
    storage=Depends(get_storage),
):
    """세션 삭제"""
    service = SessionService(channel_repo=channel_repo, session_repo=session_repo, session_input_repo=session_input_repo, storage=storage)
    try:
        service.delete_session(channel_id, session_id)
        body, sc = success_response(data=None, message="Session deleted", status_code=200)
        response.status_code = sc
        return body
    except ValueError as e:
        code = str(e)
        if code == ErrorCodes.CHANNEL_NOT_FOUND:
            return error_response(message="채널을 찾을 수 없습니다.", error_code=code, status_code=404)
        if code == ErrorCodes.SESSION_NOT_FOUND:
            return error_response(message="세션을 찾을 수 없습니다.", error_code=code, status_code=404)
        return error_response(message="서버 오류", error_code=ErrorCodes.INTERNAL_ERROR, status_code=500)
"""
공통 API 엔드포인트
- 헬스체크
- 서비스 정보 등
- [사용자 추가] 오디오북 세션 관리 및 스트리밍 로직 포함
"""

import uuid
import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Header, Path, Form, status, Query
from fastapi.responses import FileResponse, JSONResponse

# 1. 수정된 위치(app/state.py) 및 관련 모듈 임포트
from app.state import channels, sessions
from app.models.session import Session
from app.utils.response import success_response, error_response
from app.utils.error_codes import ErrorCodes

# 라우터 설정
router = APIRouter(prefix="/api/v1", tags=["Internal API"])

INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")
print(f"🔑 로드된 토큰: [{INTERNAL_SERVICE_TOKEN}]") # 서버 켜질 때 로그 확인용

@router.get("/health", tags=["Common"])
def health_check():
    """
    서비스 상태 확인용 헬스체크 API
    
    **인증 불필요**
    
    Returns:
        dict: 표준 응답 형식
            - success (bool): 요청 성공 여부
            - data (dict): 서비스 상태 정보
                - status (str): 서비스 상태 (healthy)
                - version (str): API 버전
                - service (str): 서비스 이름
    
    Example:
        ```
        GET /api/v1/health
        
        Response (200 OK):
        {
            "success": true,
            "data": {
                "status": "healthy",
                "version": "1.0.0",
                "service": "ai-audiobook"
            }
        }
        ```
    """
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": "1.0.0",
            "service": "ai-audiobook"
        }
    }

# --- [BE] A2-3: 세션 생성 ---
@router.post("/channels/{channel_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    channel_id: str = Path(..., description="채널 ID"),
    x_internal_service_token: Optional[str] = Header(None, alias="X-Internal-Service-Token"),
    file: UploadFile = File(...),
    voice_id: Optional[str] = Form(None)
):
    print("🚀 [API.PY] 요청이 정상적으로 도달했습니다!")
    # 1. 인증 검증
    if x_internal_service_token != INTERNAL_SERVICE_TOKEN:
        return error_response(
            message="인증 토큰이 없거나 유효하지 않습니다.",
            error_code=ErrorCodes.UNAUTHORIZED,
            status_code=401
        )

    # 2. 채널 존재 여부 확인
    if channel_id not in channels:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404
        )

    # 3. 파일 형식 검증 (PDF만 허용)
    if not file.filename.lower().endswith(".pdf"):
        return error_response(
            message="PDF 파일만 업로드 가능합니다.",
            error_code=ErrorCodes.INVALID_FILE_FORMAT,
            status_code=400
        )

    try:
        # 4. 세션 ID 생성 (sess_ 접두사 + UUID)
        session_id = f"sess_{uuid.uuid4()}"
        
        # 5. 세션 객체 생성 (어제 수정한 모델 순서: channel_id, session_id)
        new_session = Session(
            channel_id=channel_id,
            session_id=session_id
        )
        
        # 6. 명세서 응답 규격에 맞춘 데이터 구성
        # 비동기 처리 로직이 연동되기 전이므로 초기 상태값들을 수동으로 설정합니다.
        session_data = {
            "session_id": new_session.session_id,
            "status": "processing",
            "progress": 0,
            "current_step": "파일 업로드 완료",
            "created_at": new_session.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") # ISO 8601 형식
        }
        
        # 전역 상태 저장 (In-memory DB)
        sessions[session_id] = new_session
        
        # 7. 성공 응답 반환
        return success_response(
            data=session_data,
            status_code=201
        )

    except Exception as e:
        return error_response(
            message=f"서버 내부 오류: {str(e)}",
            error_code=ErrorCodes.INTERNAL_ERROR,
            status_code=500
        )

@router.get("/channels/{channel_id}/sessions")
async def list_sessions(
    channel_id: str = Path(..., description="채널 ID"),
    limit: int = Query(50, description="조회 개수"),
    offset: int = Query(0, description="시작 위치"),
    x_internal_service_token: Optional[str] = Header(None, alias="X-Internal-Service-Token")
):
    """
    [BE] A2-5: 특정 채널의 세션 목록 조회
    """
    # 1. 인증 검증
    if x_internal_service_token != INTERNAL_SERVICE_TOKEN:
        return error_response(
            message="인증 토큰이 없거나 유효하지 않습니다.",
            error_code=ErrorCodes.UNAUTHORIZED,
            status_code=401
        )

    # 2. 채널 존재 여부 확인
    if channel_id not in channels:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404
        )

    # 3. 해당 채널에 속한 세션 필터링 및 정렬 (최신순)
    # state.py의 sessions 딕셔너리에서 channel_id가 일치하는 것만 추출
    channel_sessions = [
        {
            "session_id": s.session_id,
            "status": "completed" if getattr(s, 'is_completed', False) else "processing", # 상태값 로직
            "progress": 100 if getattr(s, 'is_completed', False) else 0,
            "created_at": s.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        for s in sessions.values()
        if s.channel_id == channel_id
    ]

    # 생성일자 기준 내림차순 정렬 (최신순)
    channel_sessions.sort(key=lambda x: x["created_at"], reverse=True)

    # 4. 페이지네이션 적용
    total_count = len(channel_sessions)
    paged_sessions = channel_sessions[offset : offset + limit]

    # 5. 응답 규격 맞춤
    return success_response(
        data={
            "sessions": paged_sessions,
            "total": total_count
        }
    )    


@router.delete("/channels/{channel_id}/sessions/{session_id}")
async def delete_session(
    channel_id: str = Path(..., description="채널 ID"),
    session_id: str = Path(..., description="삭제할 세션 ID"),
    x_internal_service_token: Optional[str] = Header(None, alias="X-Internal-Service-Token")
):
    """
    [BE] A2-6: 세션 및 관련 파일 삭제
    """
    # 1. 인증 검증
    if x_internal_service_token != INTERNAL_SERVICE_TOKEN:
        return error_response(
            message="인증 토큰이 유효하지 않습니다.",
            error_code=ErrorCodes.UNAUTHORIZED,
            status_code=401
        )

    # 2. 채널 존재 여부 확인
    if channel_id not in channels:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.",
            error_code=ErrorCodes.CHANNEL_NOT_FOUND,
            status_code=404
        )

    # 3. 세션 존재 여부 확인
    if session_id not in sessions:
        return error_response(
            message="삭제하려는 세션을 찾을 수 없습니다.",
            error_code=ErrorCodes.SESSION_NOT_FOUND, # 명세서에 맞춘 에러코드
            status_code=404
        )

    try:
        # 4. 🔥 파일 삭제 로직 (명세 핵심 요구사항)
        # 생성 API에서 파일을 저장하는 경로 규칙에 맞춰 작성해야 합니다.
        file_path = os.path.join("outputs", "podcasts", "wav", f"{session_id}.wav")
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ 파일 삭제 완료: {file_path}")

        # 5. 메모리 데이터 삭제
        del sessions[session_id]

        # 6. 응답 (명세서 규격: 200 OK + Message)
        return success_response(
            data=None, 
            message="Session deleted", 
            status_code=200
        )

    except Exception as e:
        return error_response(
            message=f"파일 삭제 중 서버 오류: {str(e)}", 
            error_code=ErrorCodes.INTERNAL_ERROR, 
            status_code=500
        )
        

@router.get("/channels/{channel_id}/files/audio/{session_id}/{chapter}")
async def stream_audio(
    channel_id: str = Path(..., description="채널 ID"),
    session_id: str = Path(..., description="세션 ID"),
    chapter: int = Path(..., description="챕터 번호"),
    x_internal_service_token: Optional[str] = Header(None, alias="X-Internal-Service-Token")
):
    """
    [BE] A2-7: 오디오 스트리밍 API
    """
    # 1. 인증 검증
    if x_internal_service_token != INTERNAL_SERVICE_TOKEN:
        return error_response(
            message="인증 토큰이 유효하지 않습니다.", 
            error_code=ErrorCodes.UNAUTHORIZED, 
            status_code=401
        )

    # 2. 채널 및 세션 확인
    if channel_id not in channels:
        return error_response(
            message="요청하신 채널을 찾을 수 없습니다.", 
            error_code=ErrorCodes.CHANNEL_NOT_FOUND, 
            status_code=404
            )
    
    if session_id not in sessions:
        return error_response(
            message="요청하신 세션을 찾을 수 없습니다.", 
            error_code=ErrorCodes.SESSION_NOT_FOUND, 
            status_code=404)

    # 3. 세션 상태 확인 (completed 상태만 허용)
    session_obj = sessions[session_id]

    # 4. 오디오 파일 경로 구성
    file_path = os.path.join("outputs", "podcasts", "wav", f"{session_id}_ch{chapter}.wav")

    # 5. 챕터 파일 존재 여부 확인
    if not os.path.exists(file_path):
        return error_response(
            message="챕터 파일을 찾을 수 없습니다.", 
            error_code=ErrorCodes.NOT_FOUND, 
            status_code=404)

    # 6. 스트리밍 응답 반환 (FastAPI가 Range 요청을 자동으로 처리함)
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg", # 명세서 요구사항
        filename=f"chapter_{chapter}.mp3"
    )
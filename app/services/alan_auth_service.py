# app/services/alan_auth_service.py
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

import httpx
from fastapi import HTTPException, Request

from config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlanUser:
    """인증된 Alan 사용자 정보"""
    id: str
    role: str


def _extract_alan_token(request: Request) -> Optional[str]:
    """
    Request에서 Alan 토큰 추출
    우선순위: alan_session_id > alan_guest_token > Authorization Bearer
    """
    # 1. Cookie에서 alan_session_id 확인
    token = request.cookies.get("alan_session_id")
    if token:
        logger.debug("alan_session_id 쿠키에서 토큰 추출")
        return token

    # 2. Cookie에서 alan_guest_token 확인
    token = request.cookies.get("alan_guest_token")
    if token:
        logger.debug("alan_guest_token 쿠키에서 토큰 추출")
        return token

    # 3. Authorization Bearer 헤더 확인
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip() or None
        if token:
            logger.debug("Authorization 헤더에서 토큰 추출")
            return token

    return None


async def verify_alan_user(request: Request) -> AlanUser:
    """
    Auth 서버 /verify 호출로 유저 식별자(id), role 확보
    
    Returns:
        AlanUser: 인증된 사용자 정보
        
    Raises:
        HTTPException: 인증 실패 시 401, 서버 오류 시 500 또는 502
    """

    # [임시 디버그] 설정값 출력
    print(f"🔍 [DEBUG] auth_mode: '{settings.auth_mode}'")
    print(f"🔍 [DEBUG] is_mock_mode: {settings.is_mock_mode}")
    print(f"🔍 [DEBUG] alan_auth_base_url: '{settings.alan_auth_base_url}'")
    
    # Mock 모드: 개발 편의를 위한 가상 사용자 반환
    if settings.is_mock_mode:
        logger.info("Mock 모드: 테스트용 Pro 사용자 반환")
        return AlanUser(id="mock-user-id", role="pro_user")

    # Alan Auth Base URL 검증
    if not settings.alan_auth_base_url:
        logger.error("ALAN_AUTH_BASE_URL이 설정되지 않음")
        raise HTTPException(
            status_code=500,
            detail="인증 서비스가 설정되지 않았습니다"
        )

    # 토큰 추출
    token = _extract_alan_token(request)
    if not token:
        logger.warning("요청에서 유저 인증 토큰을 찾을 수 없음")
        raise HTTPException(
            status_code=401,
            detail="인증 토큰이 누락되었습니다"
        )

    # Auth 서버 /verify 호출
    verify_url = f"{settings.alan_auth_base_url.rstrip('/')}/verify"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            logger.debug(f"인증 서버 호출: {verify_url}")
            resp = await client.post(verify_url, json={"token": token})
    except httpx.TimeoutException:
        logger.error(f"인증 서버 타임아웃: {verify_url}")
        raise HTTPException(
            status_code=502,
            detail="인증 서비스 응답 시간 초과"
        )
    except httpx.RequestError as e:
        logger.error(f"인증 서버 연결 실패: {e}")
        raise HTTPException(
            status_code=502,
            detail="인증 서비스에 연결할 수 없습니다"
        )

    # 응답 상태 코드 확인
    if resp.status_code == 401:
        logger.warning("인증 서버에서 토큰 검증 실패")
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다")
    elif resp.status_code != 200:
        logger.error(f"인증 서버 예상치 못한 응답: {resp.status_code}")
        raise HTTPException(
            status_code=502,
            detail="인증 서비스 오류"
        )

    # 응답 파싱
    try:
        data: Dict[str, Any] = resp.json()
    except Exception as e:
        logger.error(f"인증 응답 파싱 실패: {e}")
        raise HTTPException(
            status_code=502,
            detail="인증 응답 형식이 올바르지 않습니다"
        )

    # 필수 필드 검증
    user_id = data.get("id")
    role = data.get("role")

    if not user_id or not role:
        logger.error(f"인증 응답 필드 누락: {data}")
        raise HTTPException(
            status_code=502,
            detail="인증 응답 형식이 올바르지 않습니다"
        )

    logger.info(f"사용자 인증 완료: id={user_id}, role={role}")
    return AlanUser(id=str(user_id), role=str(role))
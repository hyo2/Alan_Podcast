# app/dependencies/auth.py
import logging
from fastapi import Depends, HTTPException, Request

from config import settings
from app.services.alan_auth_service import AlanUser, verify_alan_user

logger = logging.getLogger(__name__)


async def get_current_user(request: Request) -> AlanUser:
    """
    현재 인증된 사용자 정보 반환
    모든 인증 필요 엔드포인트에서 사용
    """
    return await verify_alan_user(request)


async def get_current_user_id(user: AlanUser = Depends(get_current_user)) -> str:
    """사용자 ID만 필요한 경우 사용"""
    return user.id


async def require_access(user: AlanUser = Depends(get_current_user)) -> AlanUser:
    """
    접근 권한 검증
    
    접근 정책:
    - ACCESS_POLICY=pro_only  -> Pro allowlist role만 허용
    - ACCESS_POLICY=all       -> 인증만 통과하면 모든 사용자 허용
    
    Pro 판별 기준:
    - PRO_ROLE_ALLOWLIST 환경변수에 정의된 role 목록
    - 기본값: ["pro_user", "internal_user", "pro_user_promotion"]
    
    Returns:
        AlanUser: 접근 권한이 있는 사용자
        
    Raises:
        HTTPException: 접근 정책이 Pro 전용 정책 + 사용자가 Pro가 아닌 경우 403
    """
    
    # pro_only 정책인 경우에만 Pro 여부 체크
    if settings.is_pro_only_policy:
        if not settings.is_pro_role(user.role):
            logger.warning(
                f"접근 거부 - Pro 전용 정책. user_id={user.id}, role={user.role}"
            )
            raise HTTPException(
                status_code=403,
                detail="Pro 구독이 필요한 기능입니다"
            )
        logger.info(f"Pro 사용자 접근 허용: user_id={user.id}, role={user.role}")
    else:
        logger.debug(f"모든 사용자 접근 허용: user_id={user.id}, role={user.role}")

    return user


async def require_pro_user(user: AlanUser = Depends(get_current_user)) -> AlanUser:
    """
    Pro 사용자만 허용 (ACCESS_POLICY와 무관하게 강제)
    특정 엔드포인트에서 명시적으로 Pro 전용 기능을 만들 때 사용
    
    Returns:
        AlanUser: Pro 사용자
        
    Raises:
        HTTPException: Pro가 아닌 경우 403
    """
    if not settings.is_pro_role(user.role):
        logger.warning(
            f"Pro 기능 접근 거부. user_id={user.id}, role={user.role}"
        )
        raise HTTPException(
            status_code=403,
            detail="Pro 구독이 필요한 기능입니다"
        )
    
    logger.info(f"Pro 기능 접근 허용: user_id={user.id}, role={user.role}")
    return user
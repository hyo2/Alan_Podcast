"""
내부 서비스 인증 미들웨어
"""

from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """
    내부 서비스 요청을 인증하기 위한 미들웨어
    
    -요청 헤더의 X-Internal-Service-Token 값 확인
    - 환경 변수(INTERNAL_SERVICE_TOKEN)과 비교해 인증
    """
    
    def __init__(self, app, exclude_paths: list[str] = None):
        super().__init__(app)
        self.internal_token = os.getenv("INTERNAL_SERVICE_TOKEN")
        self.exclude_paths = exclude_paths or []
        
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        요청 처리 및 내부 서비스 토큰 검증
        
        Args:
            request: 들어오는 요청 객체
            call_next: 다음 미들웨어 또는 라우트 핸들러
            
        Returns:
            다음 핸들러의 응답 또는 401 에러 응답
        """
        # exclude_paths에 해당하면 인증 건너뜀
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # 요청 헤더에서 토큰 추출
        token = request.headers.get("X-Internal-Service-Token")
        
        # 토큰 검증
        if not self._validate_token(token):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "data": None,
                    "message": "Invalid or missing authentication token",
                    "error_code": "UNAUTHORIZED"
                }
            )
        
        # 검증 성공 시 다음 핸들러로
        response = await call_next(request)
        return response
    
    def _validate_token(self, token: str | None) -> bool:
        """
        내부 서비스 토큰 검증
        
        Args:
            token: 요청 헤더에서 추출한 토큰
            
        Returns:
            유효하면 True, 아니면 Fasle
        """
        # 1. 환경변수가 설정되지 않은 경우
        if not self.internal_token:
            return False
        
        # 2. 헤더에 토큰이 없는 경우
        if not token:
            return False
        
        # 3. 토큰 비교 (단순 문자열 비교)
        return token == self.internal_token
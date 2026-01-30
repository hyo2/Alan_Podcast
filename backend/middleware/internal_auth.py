"""
내부 서비스 인증 미들웨어
"""

from typing import Callable
import os

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.error_codes import ErrorCodes
from app.utils.response import error_response


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """
    내부 서비스 요청 인증 미들웨어

    - 요청 헤더의 X-Internal-Service-Token 값을 검사
    - 환경변수 INTERNAL_SERVICE_TOKEN과 일치하면 통과
    - 실패 시 공통 error_response 스펙으로 401 반환
    """

    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        # 내부 토큰은 환경변수에서 읽는다.
        self.internal_token = os.getenv("INTERNAL_SERVICE_TOKEN")
        self.exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        요청 처리 및 내부 서비스 토큰 검증
        통과하면 다음 핸들러로 넘김
        """
        path = request.url.path

        # 1) 제외 경로는 인증 검사 없이 통과
        #    (예: /docs, /openapi.json, /health 등)
        if any(path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # 2) 헤더에서 토큰 추출
        token = request.headers.get("X-Internal-Service-Token")

        # 3) 토큰 검증
        #    - 토큰이 없거나
        #    - 환경변수 토큰이 비어있거나
        #    - 값이 일치하지 않으면 401
        if not token or not self.internal_token or token != self.internal_token:
            body, status_code = error_response(
                message="Invalid or missing authentication token",
                error_code=ErrorCodes.UNAUTHORIZED,
                status_code=401
            )
            return JSONResponse(status_code=status_code, content=body)

        # 4) 통과 시 다음 핸들러 실행
        return await call_next(request)

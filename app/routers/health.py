# backend/app/routers/health.py
"""
공통 API 엔드포인트
- 헬스체크
- 서비스 정보 등
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.utils.response import success_response  # 표준 래퍼

router = APIRouter(tags=["common_health_check"])

@router.get("/v1/health")
def health_check():
    data = {
        "status": "healthy",
        "version": "1.0.0",
        "service": "ai-audiobook",
    }
    body, status_code = success_response(data, status_code=200)
    return JSONResponse(content=body, status_code=status_code)

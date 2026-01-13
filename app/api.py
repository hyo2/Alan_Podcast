"""
공통 API 엔드포인트
- 헬스체크
- 서비스 정보 등
"""

from fastapi import APIRouter

# 공통 엔드포인트를 묶기 위한 라우터
router = APIRouter(tags=["Common"])


@router.get("/v1/health")
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
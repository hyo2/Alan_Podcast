# 응답 유틸리티 함수
# backend/utils/response.py

from typing import Any, Optional, Dict, Tuple


# 성공 응답 유틸리티 함수

def success_response(
    data: Any, 
    message: Optional[str] = None, 
    status_code: int = 200
) -> Tuple[Dict[str, Any], int]:
    """
    모든 API에서 일관된 성공 응답 형식을 생성하는 래퍼 함수
    
    반환 형식:
    {
        "success": True,
        "data": { ... },
        "message": "optional message"
    }
    """
    
    # 응답 바디 구성
    response_body = {
        "success": True,
        "data": data,
        "message": message
    }
    
    return response_body, status_code



# 에러 응답 유틸리티 함수

def error_response(
    message: str, 
    error_code: str, 
    status_code: int = 400
) -> Tuple[Dict[str, Any], int]:
    """
    모든 API에서 일관된 에러 응답 형식을 생성하는 래퍼 함수
    
    반환 형식:
    {
        "success": False,
        "data": None,
        "message": "에러 메시지",
        "error_code": "ERROR_CODE"
    }
    """
    
    # 명세서의 "응답 형식" 구조를 엄격히 준수
    response_body = {
        "success": False,
        "data": None,             # 에러 응답 시 data는 항상 null(None)
        "message": message,
        "error_code": error_code
    }
    
    return response_body, status_code
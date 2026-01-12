# backend/utils/error_codes.py

from enum import Enum

# 에러 코드 상수 정의

class ErrorCodes(str, Enum):
    """
    표준화된 에러 코드 상수 정의 (공통)
    Enum 상속 시 str을 함께 사용하면 문자열처럼 직접 사용 가능
    """
    UNAUTHORIZED = "UNAUTHORIZED"               # 인증 실패 (401)
    NOT_FOUND = "NOT_FOUND"                     # 일반 리소스 없음 (404)
    CHANNEL_NOT_FOUND = "CHANNEL_NOT_FOUND"     # 채널 없음 (404)
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"     # 세션 없음 (404)
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT" # 지원하지 않는 파일 형식 (400)
    PROCESSING_FAILED = "PROCESSING_FAILED"     # 처리 중 오류 발생 (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"           # 서버 내부 오류 (500)
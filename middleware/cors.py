"""
환경별 접근 제어를 위한 CORS 미들웨어 설정

CORS 설정 스펙:
  - development: 모든 origin 허용 (*)
  - staging: gepeto-api-function stage URL만 허용
  - production: gepeto-api-function prod URL만 허용

허용 메서드: GET, POST, DELETE, OPTIONS
허용 헤더: Content-Type, X-Internal-Service-Token
자격 증명: 불필요 (credentials: false)
"""

import os
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 스펙: 허용할 HTTP 메서드 / 헤더
ALLOWED_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Content-Type", "X-Internal-Service-Token"]


def _parse_origins(raw: Optional[str]) -> List[str]:
    """
    콤마(,)로 구분된 origin 문자열을 리스트로 변환
    
    Args:
        raw: 콤마로 구분된 origin 문자열
        
    Returns:
        origin 리스트
        
    Example:
        >>> _parse_origins("https://a.com, https://b.com")
        ['https://a.com', 'https://b.com']
    """
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_app_env() -> str:
    """
    현재 애플리케이션 실행 환경을 판별
    
    ENVIRONMENT 환경변수 사용:
      - development (기본값)
      - staging
      - production
      
    Returns:
        환경 이름 (development | staging | production)
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    # 별칭 정규화
    alias = {
        "dev": "development",
        "local": "development",
        "prod": "production",
        "stage": "staging",
    }
    return alias.get(env, env)


def setup_cors(app: FastAPI) -> None:
    """
    FastAPI 앱에 환경별 CORS 설정을 적용

    스펙:
      - development: 모든 origin 허용 (*)
      - staging/production: CORS_ORIGINS에 지정된 origin만 허용

    환경 변수:
      - ENVIRONMENT: development|staging|production
      - CORS_ORIGINS: 허용 origin 목록 (콤마 구분)
    """
    env = get_app_env()

    if env == "development":
        allow_origins = ["*"]
    elif env in ("staging", "production"):
        allow_origins = _parse_origins(os.getenv("CORS_ORIGINS", ""))
        if not allow_origins:
            print(
                f"⚠️  CORS 설정 경고\n"
                f"   - 환경: {env}\n"
                f"   - CORS_ORIGINS가 비어있습니다\n"
                f"   - 모든 요청이 CORS 에러로 차단됩니다"
            )
    else:
        allow_origins = []
        print(f"⚠️  알 수 없는 환경: {env}, CORS 모든 요청 차단")

    print(f"🌐 CORS 설정 완료 → env={env}, allow_origins={allow_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        max_age=600,
    )

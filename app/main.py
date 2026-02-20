# app/main.py
import os
import logging
from pathlib import Path

from app.utils.logging_helper import setup_logging
setup_logging()
logger = logging.getLogger(__name__)


from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.utils.binary_helper import prepare_ffmpeg_binaries
from config import settings
from app.utils.error_codes import ErrorCodes
from app.utils.response import error_response
from middleware.internal_auth import InternalAuthMiddleware
from middleware.cors import setup_cors

# 라우터 import는 로깅 셋업 이후
from app.routers import channels, sessions, health, streaming

setup_logging()
logger = logging.getLogger(__name__)

def init_ffmpeg() -> None:
    """
    부팅 시점에 ffmpeg/ffprobe를 /tmp로 복사+권한 부여하고,
    pydub이 사용할 수 있게 경로를 미리 세팅
    - Flex 환경에서 /tmp 휘발성/재시작에 대비
    - pydub가 먼저 로드되어도 경고/실패 확률을 줄임
    """
    try:
        ffmpeg_path, ffprobe_path = prepare_ffmpeg_binaries()

        # pydub을 쓰는 코드 경로가 있으면 미리 지정해두는 게 안전
        try:
            from pydub import AudioSegment
            AudioSegment.converter = ffmpeg_path
            # ffprobe 지정(버전/환경에 따라 속성이 없을 수도 있어 try)
            try:
                AudioSegment.ffprobe = ffprobe_path
            except Exception:
                pass
        except Exception:
            # pydub이 requirements에 없거나 import 타이밍이 애매해도, ffmpeg 준비만 해두면 됨
            pass

        # PATH에도 /tmp/bin을 올려서 "ffprobe not found" 류 방지
        tmp_bin = str(Path(ffprobe_path).parent)  # /tmp/bin
        os.environ["PATH"] = tmp_bin + ":" + os.environ.get("PATH", "")

        # 보조 env (다른 라이브러리/코드 경로 대비)
        os.environ["FFMPEG_BINARY"] = ffmpeg_path
        os.environ["FFPROBE_BINARY"] = ffprobe_path

        logger.info("✅ FFmpeg init done at startup: %s", ffmpeg_path)
    except Exception:
        logger.exception("⚠️ FFmpeg init failed at startup (continue).")

init_ffmpeg()

app = FastAPI(
    title="ai-audiobook API",
    description="ai-audiobook API description",
    version="1.0.0",
    redirect_slashes=False
)

# ========================================
# 출력 디렉토리 설정
# ========================================
BASE_OUTPUT_DIR = os.getenv("BASE_OUTPUT_DIR", os.path.abspath("outputs"))
os.environ["BASE_OUTPUT_DIR"] = BASE_OUTPUT_DIR

REQUIRED_DIRS = [
    BASE_OUTPUT_DIR,
    os.path.join(BASE_OUTPUT_DIR, "podcasts"),
    os.path.join(BASE_OUTPUT_DIR, "podcasts", "wav"),
]

for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)
    logger.info("✅ 디렉토리 생성: %s", d)

# ========================================
# 전역 예외 핸들러
# ========================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # status code 기준으로 공통 error_code 매핑
    if exc.status_code == 401:
        code = ErrorCodes.UNAUTHORIZED
    elif exc.status_code == 404:
        code = ErrorCodes.NOT_FOUND
    else:
        code = ErrorCodes.INTERNAL_ERROR

    body, status_code = error_response(
        message=str(exc.detail),
        error_code=code,
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=status_code, content=body)

# ========================================
# 미들웨어 설정
# ========================================

# CORS 미들웨어 (환경별 설정)
setup_cors(app)

# Internal Auth 미들웨어
app.add_middleware(
    InternalAuthMiddleware,
    exclude_paths=[
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/health",
        "/assets",
        "/alan_favicon.svg"
    ]
)

# ========================================
# 라우터 등록
# ========================================

# 공통 API
app.include_router(health.router, prefix="/api")

# API routers
app.include_router(channels.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(streaming.router, prefix="/api")
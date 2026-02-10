# app/main.py
import os, logging, sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request, HTTPException

# 환경변수 로드
from config import settings

from app.utils.error_codes import ErrorCodes
from app.utils.response import error_response
from middleware.internal_auth import InternalAuthMiddleware
from middleware.cors import setup_cors

from app.routers import (
    channels, sessions, health, streaming
)

def init_logging() -> None:
    # env별로 LOG_LEVEL 변경
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_str, logging.INFO)

    # root logger를 강제로 stdout로 통일
    root = logging.getLogger()
    root.setLevel(level)

    # basicConfig가 무시되는 케이스 방지: 기존 핸들러 제거 후 재부착
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    ))
    root.addHandler(handler)

    # noisy third-party loggers는 dev에서도 WARNING로 올려서 조용히
    NOISY_LOGGERS = [
        # pdfplumber가 사용하는 pdfminer.six 쪽
        "pdfminer",
        "pdfminer.psparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfparser",
        "pdfminer.cmapdb",
        "pdfminer.pdfinterp",
        "pdfminer.converter",
        "pdfminer.layout",

        # 필요하면 추가
        "pdfplumber",
        "PIL",
        "pypdfium2",
    ]
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Azure SDK 로그는 헤더/HTTP dump가 많아서 WARNING으로 제한
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("azure.storage").setLevel(logging.WARNING)

    # uvicorn 로거도 동일 레벨로 정렬
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)

    logging.getLogger(__name__).info("logging initialized (LOG_LEVEL=%s)", log_level_str)

init_logging()
logger = logging.getLogger(__name__)

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
        "/mobile",
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

# ========================================
# Frontend (mobile only)
# ========================================
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
FAVICON_PATH = STATIC_DIR / "alan_favicon.svg"

app.mount(
    "/assets",
    StaticFiles(directory=str(STATIC_DIR / "assets")),
    name="assets"
)


@app.get("/alan_favicon.svg")
def favicon():
    if not FAVICON_PATH.is_file():
        raise HTTPException(status_code=404, detail=f"favicon not found: {FAVICON_PATH}")
    return FileResponse(FAVICON_PATH, media_type="image/svg+xml")


@app.get("/mobile")
def serve_mobile():
    return FileResponse("app/static/index.html")


@app.get("/mobile/{path:path}")
def serve_mobile_spa(path: str):
    return FileResponse("app/static/index.html")
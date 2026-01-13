# app/main.py
from pathlib import Path
from . import api
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
import os

# 환경변수 로드 (가장 먼저 실행)
from config import settings

from app.routers import auth, input, output, project, storage, voice
from app.utils.vertex_env_patch import patch_vertex_ai_env
from middleware.internal_auth import InternalAuthMiddleware
from middleware.cors import setup_cors

patch_vertex_ai_env()

app = FastAPI(
    title="AI Pods API",
    description="AI Pods API description",
    version="1.0.0",
    redirect_slashes=False
)

# Railway 환경 감지 및 경로 설정
IS_RAILWAY = (
    os.getenv("RAILWAY_ENVIRONMENT") is not None or 
    os.getenv("RAILWAY_PROJECT_ID") is not None or
    os.getenv("RAILWAY_SERVICE_NAME") is not None
)

if IS_RAILWAY:
    BASE_OUTPUT_DIR = "/tmp/outputs"
    print("🚂 Railway 환경 감지: /tmp/outputs 사용")
else:
    BASE_OUTPUT_DIR = os.path.abspath("outputs")
    print("💻 로컬 환경 감지: ./outputs 사용")

os.environ["BASE_OUTPUT_DIR"] = BASE_OUTPUT_DIR

REQUIRED_DIRS = [
    BASE_OUTPUT_DIR,
    os.path.join(BASE_OUTPUT_DIR, "podcasts"),
    os.path.join(BASE_OUTPUT_DIR, "podcasts", "wav"),
]

for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)
    print(f"✅ 디렉토리 생성: {d}")

# ========================================
# 미들웨어 설정
# ========================================

# CORS 미들웨어 (환경별 설정)
setup_cors(app)

# Internal Auth 미들웨어 추가
# 인증 제외 경로: docs, health check, frontend 등
app.add_middleware(
    InternalAuthMiddleware,
    exclude_paths=[
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/health",      # 헬스체크는 인증 불필요 (공개 엔드포인트)
        "/mobile",
        "/assets",
        "/alan_favicon.svg"
    ]
)

# ========================================
# 라우터 등록
# ========================================

# 공통 API (헬스체크 등)
app.include_router(api.router, prefix="/api")

# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(input.router, prefix="/api")
app.include_router(output.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(storage.router, prefix="/api")

# Frontend (mobile only)
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
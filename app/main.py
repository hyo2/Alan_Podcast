# app/main.py
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

# 환경변수 로드
from config import settings
# print("DATABASE_URL (masked) =", os.getenv("DATABASE_URL", "")[:60])

from app.routers import (
    auth, channels, input, output, project, sessions,
    storage, voice, health, streaming
)
from app.utils.vertex_env_patch import patch_vertex_ai_env
from middleware.internal_auth import InternalAuthMiddleware
from middleware.cors import setup_cors

patch_vertex_ai_env()

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
    print(f"✅ 디렉토리 생성: {d}")

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
app.include_router(auth.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(input.router, prefix="/api")
app.include_router(output.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(storage.router, prefix="/api")
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
"""Azure Functions entry point"""

import sys
import os

# Windows 콘솔 UTF-8 강제 (전역 설정)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import azure.functions as func
from app.main import app as fastapi_app

# Azure Functions HTTP 트리거로 FastAPI 래핑
app = func.AsgiFunctionApp(
    app=fastapi_app,
    http_auth_level=func.AuthLevel.ANONYMOUS
)
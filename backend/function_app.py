"""Azure Functions entry point (Python programming model v2)"""

import os, json, tempfile, pathlib
import logging
import base64
import azure.functions as func

logger = logging.getLogger(__name__)

def _ensure_vertex_sa_file():
    target = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE", "/tmp/gcp-sa.json")

    try:
        # 이미 파일 있으면 그대로 사용
        if pathlib.Path(target).exists():
            return target

        sa = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
        if not sa:
            logger.warning("VERTEX_AI_SERVICE_ACCOUNT_JSON not set. Skipping file creation.")
            return None

        data = json.loads(sa)

        pathlib.Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f)

        return target

    except Exception as e:
        logger.exception("Failed to ensure Vertex service account file: %s", e)
        return None

# 절대 여기서 raise하지 않도록 유지
_ensure_vertex_sa_file()


# ========================================
# 1. FastAPI ASGI Wrapper (HTTP 트리거)
# ========================================
from app.main import app as fastapi_app

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="http_app_func")
@app.route(route="{*route}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def http_app_func(req: func.HttpRequest) -> func.HttpResponse:
    """FastAPI를 Azure Functions HTTP 트리거로 래핑"""
    return await func.AsgiMiddleware(fastapi_app).handle_async(req)


# ========================================
# 2. Queue Trigger (백그라운드 워커)
# ========================================
_QUEUE_NAME = os.getenv("AZURE_STORAGE_QUEUE_NAME", "ai-audiobook-jobs")


@app.function_name(name="session_job_worker")
@app.queue_trigger(
    arg_name="msg",
    queue_name=_QUEUE_NAME,
    connection="AzureWebJobsStorage",
)
def session_job_worker(msg: func.QueueMessage) -> None:
    """큐에서 세션 처리 작업을 가져와 실행"""
    
    raw = msg.get_body().decode("utf-8", errors="replace")
    logger.info("[Queue] Received message: %s", raw[:200])
    from app.services.pipeline_worker import handle_queue_message
    handle_queue_message(raw)
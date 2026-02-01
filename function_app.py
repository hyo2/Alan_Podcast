"""Azure Functions entry point (Python programming model v2)"""

import os
import json
import logging
import azure.functions as func

logger = logging.getLogger(__name__)

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

    try:
        payload = json.loads(raw)
    except Exception:
        logger.exception("[Queue] Invalid JSON message")
        return

    kind = payload.get("kind", "generate")
    if kind != "generate":
        logger.warning("[Queue] Unknown kind=%s. skipping", kind)
        return

    session_id = payload.get("session_id")
    channel_id = payload.get("channel_id")
    options = payload.get("options") or {}

    if not session_id or not channel_id:
        logger.warning("[Queue] Missing session_id/channel_id. payload=%s", payload)
        return

    logger.info(f"[Queue] Processing session_id={session_id}, channel_id={channel_id}")

    try:
        from app.dependencies.repos import (
            get_db,
            get_channel_repo,
            get_session_repo,
            get_session_input_repo,
        )
        from app.services.storage_service import get_storage
        from app.services.session_service import SessionService

        storage = get_storage()
        backend = os.getenv("REPO_BACKEND", "memory").lower().strip()

        if backend == "postgres":
            db_gen = get_db()
            db = next(db_gen)
            try:
                channel_repo = get_channel_repo(db=db)
                session_repo = get_session_repo(db=db)
                session_input_repo = get_session_input_repo(db=db)

                service = SessionService(
                    channel_repo=channel_repo,
                    session_repo=session_repo,
                    session_input_repo=session_input_repo,
                    storage=storage,
                )
                _run_service(service, session_id, channel_id, options)
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
        else:
            channel_repo = get_channel_repo(db=None)
            session_repo = get_session_repo(db=None)
            session_input_repo = get_session_input_repo(db=None)

            service = SessionService(
                channel_repo=channel_repo,
                session_repo=session_repo,
                session_input_repo=session_input_repo,
                storage=storage,
            )
            _run_service(service, session_id, channel_id, options)

        logger.info(f"[Queue] ✅ Successfully processed session_id={session_id}")

    except Exception as e:
        logger.exception(f"[Queue] ❌ Worker failed for session_id={session_id}: {str(e)}")


def _run_service(service, session_id: str, channel_id: str, options: dict) -> None:
    """비동기 함수를 동기 컨텍스트에서 실행"""
    import asyncio
    import inspect

    fn = service.process_audiobook_generation

    if inspect.iscoroutinefunction(fn):
        # 비동기 함수인 경우 asyncio.run으로 실행
        try:
            asyncio.run(fn(session_id=session_id, channel_id=channel_id, options=options))
        except Exception as e:
            logger.error(f"[Queue] asyncio.run failed: {e}")
            raise
    else:
        # 동기 함수인 경우 바로 실행
        fn(session_id=session_id, channel_id=channel_id, options=options)
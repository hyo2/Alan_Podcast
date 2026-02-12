# app/services/pipeline_worker.py
# Queue 메시지 처리/오케스트레이션만 담당
import os, json, base64, logging

logger = logging.getLogger(__name__)

_QUEUE_NAME = os.getenv("AZURE_STORAGE_QUEUE_NAME", "ai-audiobook-jobs")

def parse_queue_payload(raw: str) -> dict | None:
    try:
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return json.loads(raw)
    except Exception:
        logger.exception("[Queue] Invalid JSON message")
        return None

def _run_service(service, session_id: str, channel_id: str, options: dict) -> None:
    import asyncio, inspect
    fn = service.process_audiobook_generation
    if inspect.iscoroutinefunction(fn):
        asyncio.run(fn(session_id=session_id, channel_id=channel_id, options=options))
    else:
        fn(session_id=session_id, channel_id=channel_id, options=options)

def handle_full_pipeline(payload: dict) -> None:
    session_id = payload.get("session_id")
    channel_id = payload.get("channel_id")
    options = payload.get("options") or {}
    if not session_id or not channel_id:
        logger.warning("[Queue] Missing session_id/channel_id")
        return

    from app.dependencies.repos import get_db, get_channel_repo, get_session_repo, get_session_input_repo
    from app.services.storage_service import get_storage
    from app.services.session_service import SessionService

    storage = get_storage()
    backend = os.getenv("REPO_BACKEND", "memory").lower().strip()
    logger.info(f"[Queue] Full pipeline: session_id={session_id}")

    try:
        if backend == "postgres":
            db_gen = get_db()
            db = next(db_gen)
            try:
                service = SessionService(
                    channel_repo=get_channel_repo(db=db),
                    session_repo=get_session_repo(db=db),
                    session_input_repo=get_session_input_repo(db=db),
                    storage=storage,
                )
                _run_service(service, session_id, channel_id, options)
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
        else:
            service = SessionService(
                channel_repo=get_channel_repo(db=None),
                session_repo=get_session_repo(db=None),
                session_input_repo=get_session_input_repo(db=None),
                storage=storage,
            )
            _run_service(service, session_id, channel_id, options)

        logger.info(f"[Queue] ✅ Full pipeline completed: {session_id}")
    except Exception:
        logger.exception(f"[Queue] ❌ Full pipeline failed: {session_id}")
        

def handle_pipeline_step(payload: dict) -> None:
    session_id = payload.get("session_id")
    channel_id = payload.get("channel_id")
    step = payload.get("step")
    options = payload.get("options") or {}
    if not session_id or not channel_id or not step:
        logger.warning("[Queue] Missing required fields in pipeline_step")
        return

    from app.dependencies.repos import get_db, get_channel_repo, get_session_repo, get_session_input_repo
    from app.services.storage_service import get_storage
    from app.services.pipeline_steps import (
        run_extract_ocr_step,
        run_extract_finalize_step,
        run_script_step,
        run_audio_step,
        run_finalize_step,
    )

    storage = get_storage()
    backend = os.getenv("REPO_BACKEND", "memory").lower().strip()

    def execute(session_repo, session_input_repo):
        try:
            # ===== resume 가드 + 다음 step enqueue =====
            session = session_repo.get_session(session_id)
            storage_prefix = (session or {}).get("storage_prefix", "")

            def _json_exists(key: str) -> bool:
                try:
                    storage.download_json(key)
                    return True
                except Exception:
                    return False

            from app.services.queue_service import enqueue_pipeline_step

            if step == "extract_ocr":
                if _json_exists(f"{storage_prefix}pipeline/ocr_results.json"):
                    enqueue_pipeline_step(session_id, channel_id, "extract_finalize", options)
                    return
                run_extract_ocr_step(session_id, channel_id, options, storage, session_repo, session_input_repo)
                return

            if step == "extract_finalize":
                if _json_exists(f"{storage_prefix}pipeline/extracted_data.json"):
                    enqueue_pipeline_step(session_id, channel_id, "script", options)
                    return
                run_extract_finalize_step(session_id, channel_id, options, storage, session_repo)
                return

            if step == "script":
                if _json_exists(f"{storage_prefix}pipeline/script.json"):
                    enqueue_pipeline_step(session_id, channel_id, "audio", options)
                    return
                run_script_step(session_id, channel_id, options, storage, session_repo)
                return

            if step == "audio":
                if _json_exists(f"{storage_prefix}pipeline/audio_metadata.json"):
                    enqueue_pipeline_step(session_id, channel_id, "finalize", options)
                    return
                run_audio_step(session_id, channel_id, options, storage, session_repo)
                return

            if step == "finalize":
                sess = session_repo.get_session(session_id)
                if (sess or {}).get("status") == "completed" or (sess or {}).get("current_step") == "completed":
                    return
                run_finalize_step(session_id, channel_id, options, storage, session_repo)
                return

            logger.error(f"[Queue] Unknown step: {step}")

        except Exception as e:
            logger.exception(f"[Queue] ❌ Step {step} failed for session={session_id}")
            try:
                session_repo.update_session_fields(
                    session_id,
                    status="failed",
                    current_step=f"{step}_error",
                    error_message=str(e)[:500],
                )
            except Exception:
                logger.exception("Failed to update error status")

    if backend == "postgres":
        db_gen = get_db()
        db = next(db_gen)
        try:
            execute(
                session_repo=get_session_repo(db=db),
                session_input_repo=get_session_input_repo(db=db),
            )
        finally:
            try: next(db_gen)
            except StopIteration: pass
    else:
        execute(
            session_repo=get_session_repo(db=None),
            session_input_repo=get_session_input_repo(db=None),
        )

def handle_queue_message(raw: str) -> None:
    payload = parse_queue_payload(raw)
    if not payload:
        return
    kind = payload.get("kind", "generate")
    if kind == "generate":
        handle_full_pipeline(payload)
    elif kind == "pipeline_step":
        handle_pipeline_step(payload)
    else:
        logger.warning("[Queue] Unknown kind=%s. skipping", kind)
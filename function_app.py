"""Azure Functions entry point (Python programming model v2)"""

import os
import json
import logging
import base64
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
    import base64
    
    raw = msg.get_body().decode("utf-8", errors="replace")
    logger.info("[Queue] Received message: %s", raw[:200])

    try:
        # Base64 디코딩 시도 (enqueue_session_job에서 Base64 인코딩됨)
        try:
            decoded = base64.b64decode(raw).decode('utf-8')
            payload = json.loads(decoded)
        except Exception:
            # Base64가 아니면 그냥 JSON 파싱
            payload = json.loads(raw)
    except Exception:
        logger.exception("[Queue] Invalid JSON message")
        return

    kind = payload.get("kind", "generate")
    
    # 기존 방식 (호환성 유지)
    if kind == "generate":
        _handle_full_pipeline(payload)
        return
    
    # 새로운 단계별 방식
    if kind == "pipeline_step":
        _handle_pipeline_step(payload)
        return
    
    logger.warning("[Queue] Unknown kind=%s. skipping", kind)


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


def _handle_full_pipeline(payload: dict) -> None:
    """기존 전체 파이프라인 실행 (호환성 유지)"""
    session_id = payload.get("session_id")
    channel_id = payload.get("channel_id")
    options = payload.get("options") or {}

    if not session_id or not channel_id:
        logger.warning("[Queue] Missing session_id/channel_id")
        return

    logger.info(f"[Queue] Full pipeline: session_id={session_id}")

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

        logger.info(f"[Queue] ✅ Full pipeline completed: {session_id}")

    except Exception as e:
        logger.exception(f"[Queue] ❌ Full pipeline failed: {session_id}")

# ======================================
# 단계별 파이프라인 처리 함수들
# ======================================

def _handle_pipeline_step(payload: dict) -> None:
    """단계별 파이프라인 실행"""
    session_id = payload.get("session_id")
    channel_id = payload.get("channel_id")
    step = payload.get("step")
    options = payload.get("options") or {}

    if not session_id or not channel_id or not step:
        logger.warning("[Queue] Missing required fields in pipeline_step")
        return

    logger.info(f"[Queue] Pipeline step: {step} for session={session_id}")

    # DB 연결
    from app.dependencies.repos import get_db, get_channel_repo, get_session_repo, get_session_input_repo
    from app.services.storage_service import get_storage

    storage = get_storage()
    backend = os.getenv("REPO_BACKEND", "memory").lower().strip()

    if backend == "postgres":
        db_gen = get_db()
        db = next(db_gen)
        try:
            channel_repo = get_channel_repo(db=db)
            session_repo = get_session_repo(db=db)
            session_input_repo = get_session_input_repo(db=db)

            _execute_pipeline_step(
                step=step,
                session_id=session_id,
                channel_id=channel_id,
                options=options,
                storage=storage,
                session_repo=session_repo,
                session_input_repo=session_input_repo,
            )
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
    else:
        channel_repo = get_channel_repo(db=None)
        session_repo = get_session_repo(db=None)
        session_input_repo = get_session_input_repo(db=None)

        _execute_pipeline_step(
            step=step,
            session_id=session_id,
            channel_id=channel_id,
            options=options,
            storage=storage,
            session_repo=session_repo,
            session_input_repo=session_input_repo,
        )


def _execute_pipeline_step(
    step: str,
    session_id: str,
    channel_id: str,
    options: dict,
    storage,
    session_repo,
    session_input_repo,
) -> None:
    """실제 단계별 실행 로직"""
    try:
        # ===== resume(멱등) 가드 =====
        # 이미 산출물이 있으면 해당 step은 다시 실행하지 않고 다음 step을 enqueue
        session = session_repo.get_session(session_id)
        storage_prefix = (session or {}).get("storage_prefix", "")

        def _json_exists(key: str) -> bool:
            try:
                storage.download_json(key)
                return True
            except Exception:
                return False

        from app.services.queue_service import enqueue_pipeline_step

        # extract_ocr 재개: ocr_results.json 있으면 extract_finalize로
        if step == "extract_ocr":
            ocr_key = f"{storage_prefix}pipeline/ocr_results.json"
            if _json_exists(ocr_key):
                logger.info("[Resume] ocr_results exists. Skipping extract_ocr -> enqueue extract_finalize")
                enqueue_pipeline_step(session_id=session_id, channel_id=channel_id, step="extract_finalize", options=options)
                return

        # extract_finalize 재개: extracted_data.json 있으면 script로
        if step == "extract_finalize":
            extracted_key = f"{storage_prefix}pipeline/extracted_data.json"
            if _json_exists(extracted_key):
                logger.info("[Resume] extracted_data exists. Skipping extract_finalize -> enqueue script")
                enqueue_pipeline_step(session_id=session_id, channel_id=channel_id, step="script", options=options)
                return

        # script 재개: script.json 있으면 audio로
        if step == "script":
            script_key = f"{storage_prefix}pipeline/script.json"
            if _json_exists(script_key):
                logger.info("[Resume] script exists. Skipping script -> enqueue audio")
                enqueue_pipeline_step(session_id=session_id, channel_id=channel_id, step="audio", options=options)
                return

        # audio 재개: audio_metadata.json 있으면 finalize로
        if step == "audio":
            audio_meta_key = f"{storage_prefix}pipeline/audio_metadata.json"
            if _json_exists(audio_meta_key):
                logger.info("[Resume] audio_metadata exists. Skipping audio -> enqueue finalize")
                enqueue_pipeline_step(session_id=session_id, channel_id=channel_id, step="finalize", options=options)
                return

        # finalize 재개: 이미 completed면 스킵(중복 finalize 방지)
        if step == "finalize":
            sess = session_repo.get_session(session_id)
            if (sess or {}).get("status") == "completed" or (sess or {}).get("current_step") == "completed":
                logger.info("[Resume] session already completed. Skipping finalize")
                return

        # ===== 기존 로직 =====
        if step == "extract_ocr":
            _run_extract_ocr_step(session_id, channel_id, options, storage, session_repo, session_input_repo)
        elif step == "extract_finalize":
            _run_extract_finalize_step(session_id, channel_id, options, storage, session_repo)
        elif step == "script":
            _run_script_step(session_id, channel_id, options, storage, session_repo)
        elif step == "audio":
            _run_audio_step(session_id, channel_id, options, storage, session_repo)
        elif step == "finalize":
            _run_finalize_step(session_id, channel_id, options, storage, session_repo)
        else:
            logger.error(f"[Queue] Unknown step: {step}")

    except Exception as e:
        logger.exception(f"[Queue] ❌ Step {step} failed for session={session_id}")
        
        # 에러 상태 업데이트
        try:
            session_repo.update_session_fields(
                session_id,
                status="failed",
                current_step=f"{step}_error",
                error_message=str(e)[:500],
            )
        except Exception:
            logger.exception("Failed to update error status")


# ========================================
# 각 단계별 실행 함수
# ========================================

def _run_extract_ocr_step(session_id, channel_id, options, storage, session_repo, session_input_repo):
    """
    ✅ Extract Phase 1: OCR 수행
    - 입력 파일 다운로드
    - extract_texts_node() 실행 (OCR 포함)
    - OCR 결과만 Blob에 저장
    """
    import tempfile
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[ExtractOCR] Starting for session={session_id}")
    
    # 세션 삭제 체크
    if not session_exists(session_repo, session_id):
        logger.info(f"[ExtractOCR] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    # 진행 상황 업데이트
    session_repo.update_session_fields(
        session_id,
        current_step="extract_texts",
    )
    
    # 입력 파일 다운로드
    inputs = session_input_repo.list_inputs(session_id)
    if not inputs:
        raise Exception("입력 파일이 없습니다.")
    
    main_sources = []
    aux_sources = []
    temp_files = []
    
    try:
        for inp in inputs:
            if inp.get("is_link"):
                source_path = inp["link_url"]
            else:
                input_key = inp["input_key"]
                file_data = storage.download(input_key)
                
                file_ext = os.path.splitext(input_key)[1] or ".tmp"
                temp_fd, temp_path = tempfile.mkstemp(suffix=file_ext, prefix=f"input_{inp['input_id']}_")
                
                with os.fdopen(temp_fd, 'wb') as f:
                    f.write(file_data)
                
                temp_files.append(temp_path)
                source_path = temp_path
            
            if inp["role"] == "main":
                main_sources.append(source_path)
            else:
                aux_sources.append(source_path)
        
        # 체크포인트 콜백 함수 정의
        def checkpoint_callback(key: str, data: dict):
            """중간 저장 콜백 - Blob Storage에 체크포인트 저장"""
            try:
                storage.upload_json(key, data)
                logger.info(f"[ExtractOCR] 💾 Checkpoint saved: {key}")
            except Exception as e:
                logger.warning(f"[ExtractOCR] ⚠️ Checkpoint save failed: {e}")

        # LangGraph 노드 직접 호출 (OCR 수행)
        from app.langgraph_pipeline.podcast.graph import extract_texts_node
        
        state = {
            "main_sources": main_sources,
            "aux_sources": aux_sources,
            "source_data": {},
            "main_texts": [],
            "aux_texts": [],
            "combined_text": "",
            "errors": [],
            "usage": {},
            "session_id": session_id,
            "storage_prefix": storage_prefix,
            "checkpoint_callback": checkpoint_callback,
        }
        
        # ✅ OCR 수행
        state = extract_texts_node(state)
        
        if not session_exists(session_repo, session_id):
            logger.info(f"[ExtractOCR] Session {session_id} deleted during execution")
            return
        
        if state.get("errors"):
            raise Exception(f"Extract OCR failed: {state['errors']}")
        
        # ✅ OCR 결과 저장 (combine 전)
        ocr_results_key = f"{storage_prefix}pipeline/ocr_results.json"
        
        ocr_data = {
            "source_data": state["source_data"],
            "main_texts": state["main_texts"],
            "aux_texts": state["aux_texts"],
            "usage": state.get("usage", {}),
        }
        
        storage.upload_json(ocr_results_key, ocr_data)
        
        # 진행 상황 업데이트
        progress_key = f"{storage_prefix}pipeline/progress.json"
        progress_data = {
            "completed_steps": ["extract_ocr"],
            "current_step": "extract_finalize",
            "intermediate_keys": {
                "ocr_results": ocr_results_key,
            }
        }
        storage.upload_json(progress_key, progress_data)
        
        # DB 업데이트
        session_repo.update_session_fields(
            session_id,
            current_step="extract_ocr_complete",
        )
        
        logger.info(f"[ExtractOCR] ✅ Completed for session={session_id}")
        
        # ✅ 다음 단계 큐잉 (extract_finalize)
        from app.services.queue_service import enqueue_pipeline_step
        enqueue_pipeline_step(
            session_id=session_id,
            channel_id=channel_id,
            step="extract_finalize",
            options=options,
        )
        
    finally:
        # 임시 파일 정리
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass


def _run_extract_finalize_step(session_id, channel_id, options, storage, session_repo):
    """
    ✅ Extract Phase 2: 텍스트 병합 + 메타데이터 생성
    - OCR 결과 로드
    - combine_texts_node() 실행
    - 최종 extracted_data.json 저장
    """
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[ExtractFinalize] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[ExtractFinalize] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    session_repo.update_session_fields(session_id, current_step="combine_texts")
    
    # ✅ 이전 단계 결과 로드
    ocr_results_key = f"{storage_prefix}pipeline/ocr_results.json"
    ocr_data = storage.download_json(ocr_results_key)
    
    # LangGraph 노드 직접 호출
    from app.langgraph_pipeline.podcast.graph import combine_texts_node
    
    state = {
        "source_data": ocr_data["source_data"],
        "main_texts": ocr_data["main_texts"],
        "aux_texts": ocr_data["aux_texts"],
        "combined_text": "",
        "errors": [],
        "usage": ocr_data.get("usage", {}),
    }
    
    # ✅ 텍스트 병합 (빠른 작업)
    state = combine_texts_node(state)
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[ExtractFinalize] Session {session_id} deleted during execution")
        return
    
    # ✅ 최종 결과 저장
    extracted_key = f"{storage_prefix}pipeline/extracted_data.json"
    
    extracted_data = {
        "combined_text": state["combined_text"],
        "source_data": state["source_data"],
        "main_texts": state["main_texts"],
        "aux_texts": state["aux_texts"],
        "usage": state.get("usage", {}),
    }
    
    storage.upload_json(extracted_key, extracted_data)
    
    # 진행 상황 업데이트
    progress_key = f"{storage_prefix}pipeline/progress.json"
    progress_data = storage.download_json(progress_key)
    progress_data["completed_steps"].append("extract_finalize")
    progress_data["current_step"] = "script"
    progress_data["intermediate_keys"]["extracted_data"] = extracted_key
    storage.upload_json(progress_key, progress_data)
    
    # DB 업데이트
    session_repo.update_session_fields(
        session_id,
        current_step="extract_complete",
    )
    
    logger.info(f"[ExtractFinalize] ✅ Completed for session={session_id}")
    
    # ✅ 다음 단계 큐잉 (script)
    from app.services.queue_service import enqueue_pipeline_step
    enqueue_pipeline_step(
        session_id=session_id,
        channel_id=channel_id,
        step="script",
        options=options,
    )


def _run_script_step(session_id, channel_id, options, storage, session_repo):
    """2단계: 스크립트 생성"""
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Script] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Script] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    session_repo.update_session_fields(session_id, current_step="generate_script")
    
    # 이전 단계 결과 로드
    extracted_key = f"{storage_prefix}pipeline/extracted_data.json"
    extracted_data = storage.download_json(extracted_key)
    
    # LangGraph 노드 직접 호출
    from app.langgraph_pipeline.podcast.graph import generate_script_node
    
    # ✅ Vertex AI 설정
    project_id = os.getenv("VERTEX_AI_PROJECT_ID")
    region = os.getenv("VERTEX_AI_REGION")
    sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    state = {
        "combined_text": extracted_data["combined_text"],
        "source_data": extracted_data["source_data"],
        "project_id": project_id,
        "region": region,
        "sa_file": sa_file,
        "host_name": options.get("host1", "Fenrir"),
        "guest_name": options.get("host2", ""),
        "style": options.get("style", "explain"),
        "duration": options.get("duration", 5),
        "difficulty": options.get("difficulty", "intermediate"),
        "user_prompt": options.get("user_prompt", ""),
        "usage": extracted_data.get("usage", {}),
        "errors": [],
    }
    
    state = generate_script_node(state)
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Script] Session {session_id} deleted during execution")
        return
    
    if state.get("errors"):
        raise Exception(f"Script generation failed: {state['errors']}")
    
    # 스크립트 저장
    script_key = f"{storage_prefix}pipeline/script.json"
    script_data = {
        "title": state["title"],
        "script": state["script"],
        "usage": state.get("usage", {}),
    }
    storage.upload_json(script_key, script_data)
    
    # 진행 상황 업데이트
    progress_key = f"{storage_prefix}pipeline/progress.json"
    progress_data = storage.download_json(progress_key)
    progress_data["completed_steps"].append("script")
    progress_data["current_step"] = "audio"
    progress_data["intermediate_keys"]["script"] = script_key
    storage.upload_json(progress_key, progress_data)
    
    session_repo.update_session_fields(
        session_id,
        current_step="script_complete",
        title=state["title"],
    )
    
    logger.info(f"[Script] ✅ Completed for session={session_id}")
    
    # 다음 단계 큐잉
    from app.services.queue_service import enqueue_pipeline_step
    enqueue_pipeline_step(
        session_id=session_id,
        channel_id=channel_id,
        step="audio",
        options=options,
    )


def _run_audio_step(session_id, channel_id, options, storage, session_repo):
    """3단계: 오디오 생성"""
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Audio] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Audio] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    session_repo.update_session_fields(session_id, current_step="generate_audio")
    
    # 이전 단계 결과 로드
    script_key = f"{storage_prefix}pipeline/script.json"
    script_data = storage.download_json(script_key)
    
    # LangGraph 노드 직접 호출
    from app.langgraph_pipeline.podcast.graph import generate_audio_node
    
    state = {
        "script": script_data["script"],
        "host_name": options.get("host1", "Fenrir"),
        "guest_name": options.get("host2", ""),
        "usage": script_data.get("usage", {}),
        "errors": [],
    }
    
    state = generate_audio_node(state)
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Audio] Session {session_id} deleted during execution")
        return
    
    if state.get("errors"):
        raise Exception(f"Audio generation failed: {state['errors']}")
    
    # 오디오 파일들을 Blob에 업로드
    audio_parts_dir = f"{storage_prefix}pipeline/audio_parts/"
    wav_files = state["wav_files"]
    
    uploaded_audio_keys = []
    for i, wav_path in enumerate(wav_files):
        with open(wav_path, 'rb') as f:
            audio_data = f.read()
        
        audio_key = f"{audio_parts_dir}part_{i}.wav"
        storage.upload_bytes(audio_key, audio_data, content_type="audio/wav")
        uploaded_audio_keys.append(audio_key)
        
        # 로컬 임시 파일 삭제
        try:
            os.remove(wav_path)
        except Exception:
            pass
    
    # 메타데이터 저장
    audio_metadata_key = f"{storage_prefix}pipeline/audio_metadata.json"
    audio_data = {
        "audio_metadata": state["audio_metadata"],
        "audio_parts_keys": uploaded_audio_keys,
        "usage": state.get("usage", {}),
    }
    storage.upload_json(audio_metadata_key, audio_data)
    
    # 진행 상황 업데이트
    progress_key = f"{storage_prefix}pipeline/progress.json"
    progress_data = storage.download_json(progress_key)
    progress_data["completed_steps"].append("audio")
    progress_data["current_step"] = "finalize"
    progress_data["intermediate_keys"]["audio_metadata"] = audio_metadata_key
    storage.upload_json(progress_key, progress_data)
    
    session_repo.update_session_fields(session_id, current_step="audio_complete")
    
    logger.info(f"[Audio] ✅ Completed for session={session_id}")
    
    # 다음 단계 큐잉
    from app.services.queue_service import enqueue_pipeline_step
    enqueue_pipeline_step(
        session_id=session_id,
        channel_id=channel_id,
        step="finalize",
        options=options,
    )


def _run_finalize_step(session_id, channel_id, options, storage, session_repo):
    """4단계: 최종 병합 + 트랜스크립트"""
    import tempfile
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Finalize] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Finalize] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    session_repo.update_session_fields(session_id, current_step="merge_audio")
    
    # 이전 단계 결과 로드
    script_key = f"{storage_prefix}pipeline/script.json"
    audio_metadata_key = f"{storage_prefix}pipeline/audio_metadata.json"
    
    script_data = storage.download_json(script_key)
    audio_data = storage.download_json(audio_metadata_key)
    
    # 오디오 파일 다운로드
    audio_parts_keys = audio_data["audio_parts_keys"]
    temp_wav_files = []
    
    try:
        for audio_key in audio_parts_keys:
            audio_bytes = storage.download(audio_key)
            
            temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(audio_bytes)
            
            temp_wav_files.append(temp_path)
        
        # LangGraph 노드 직접 호출
        from app.langgraph_pipeline.podcast.graph import merge_audio_node, generate_transcript_node
        
        state = {
            "wav_files": temp_wav_files,
            "audio_metadata": audio_data["audio_metadata"],
            "script": script_data["script"],
            "title": script_data["title"],
            "usage": audio_data.get("usage", {}),
            "errors": [],
        }
        
        # 병합
        state = merge_audio_node(state)
        
        if not session_exists(session_repo, session_id):
            logger.info(f"[Finalize] Session {session_id} deleted during merge")
            return
        
        if state.get("errors"):
            raise Exception(f"Audio merge failed: {state['errors']}")
        
        session_repo.update_session_fields(session_id, current_step="merge_complete")
        
        # 트랜스크립트 생성
        state = generate_transcript_node(state)
        
        if not session_exists(session_repo, session_id):
            logger.info(f"[Finalize] Session {session_id} deleted during transcript")
            return
        
        # 최종 파일 업로드
        final_audio_path = state["final_podcast_path"]
        transcript_path = state["transcript_path"]
        
        output_dir = f"{storage_prefix}output_files/"
        
        # 오디오 업로드
        with open(final_audio_path, 'rb') as f:
            audio_bytes = f.read()
        audio_key = f"{output_dir}audio/{os.path.basename(final_audio_path)}"
        storage.upload_bytes(audio_key, audio_bytes, content_type="audio/mpeg")
        
        # 스크립트 업로드
        with open(transcript_path, 'rb') as f:
            script_bytes = f.read()
        script_out_key = f"{output_dir}script/{os.path.basename(transcript_path)}"
        storage.upload_bytes(script_out_key, script_bytes, content_type="text/plain")
        
        # 오디오 길이 계산
        from pydub import AudioSegment
        audio = AudioSegment.from_file(final_audio_path)
        total_duration_sec = int(len(audio) / 1000)
        
        # 스크립트 텍스트 읽기
        with open(transcript_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        # 최종 업데이트
        if not session_exists(session_repo, session_id):
            logger.info(f"[Finalize] Session {session_id} deleted before final update")
            # 업로드한 파일 삭제
            try:
                storage.delete(audio_key)
                storage.delete(script_out_key)
            except:
                pass
            return
        
        session_repo.update_session_fields(
            session_id,
            status="completed",
            current_step="completed",
            audio_key=audio_key,
            script_key=script_out_key,
            script_text=script_text,
            total_duration_sec=total_duration_sec,
        )
        
        logger.info(f"[Finalize] ✅ Completed for session={session_id}")
        
        # 임시 파일 정리
        try:
            os.remove(final_audio_path)
            os.remove(transcript_path)
        except Exception:
            pass
        
    finally:
        # WAV 파일 정리
        for temp_file in temp_wav_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
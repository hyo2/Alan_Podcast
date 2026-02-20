import os
import logging
from app.utils.binary_helper import prepare_ffmpeg_binaries
from app.services.langsmith_tracing import _get_root_run_id, _trace_with_parent

logger = logging.getLogger(__name__)

# ========================================
# 각 단계별 실행 함수
# ========================================

def run_extract_ocr_step(session_id, channel_id, options, storage, session_repo, session_input_repo):
    import tempfile
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[ExtractOCR] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[ExtractOCR] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    # ✅ Root run ID 조회
    root_run_id = _get_root_run_id(storage, storage_prefix)
    
    # 진행 상황 업데이트
    session_repo.update_session_fields(session_id, current_step="extract_texts")
    
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
        
        # 체크포인트 콜백
        def checkpoint_callback(key: str, data: dict):
            try:
                storage.upload_json(key, data)
                logger.info(f"[ExtractOCR] 💾 Checkpoint saved: {key}")
            except Exception as e:
                logger.warning(f"[ExtractOCR] ⚠️ Checkpoint save failed: {e}")

        # ✅ State 준비
        from app.langgraph_pipeline.podcast.graph import extract_texts_node
        
        state_input = {
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
        
        # ✅ Parent run으로 연결하여 node 실행
        if root_run_id:
            state = _trace_with_parent(
                name="extract_texts",
                parent_run_id=root_run_id,
                func=lambda s: extract_texts_node(s),
                state_input=state_input,
            )
        else:
            state = extract_texts_node(state_input)
        
        # 세션 삭제 체크
        if not session_exists(session_repo, session_id):
            logger.info(f"[ExtractOCR] Session {session_id} deleted during execution")
            return
        
        if state.get("errors"):
            raise Exception(f"Extract OCR failed: {state['errors']}")
        
        # OCR 결과 저장
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
        progress_data = storage.download_json(progress_key)
        progress_data["completed_steps"].append("extract_ocr")
        progress_data["current_step"] = "extract_finalize"
        progress_data["intermediate_keys"]["ocr_results"] = ocr_results_key
        storage.upload_json(progress_key, progress_data)
        
        session_repo.update_session_fields(session_id, current_step="extract_ocr_complete")
        logger.info(f"[ExtractOCR] ✅ Completed for session={session_id}")
        
        # 다음 단계 큐잉
        from app.services.queue_service import enqueue_pipeline_step
        enqueue_pipeline_step(
            session_id=session_id,
            channel_id=channel_id,
            step="extract_finalize",
            options=options,
        )
        
    finally:
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass


def run_extract_finalize_step(session_id, channel_id, options, storage, session_repo):
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
    
    # ✅ Root run ID 조회
    root_run_id = _get_root_run_id(storage, storage_prefix)
    
    session_repo.update_session_fields(session_id, current_step="combine_texts")
    
    # 이전 단계 결과 로드
    ocr_results_key = f"{storage_prefix}pipeline/ocr_results.json"
    ocr_data = storage.download_json(ocr_results_key)
    
    from app.langgraph_pipeline.podcast.graph import combine_texts_node
    
    state_input = {
        "source_data": ocr_data["source_data"],
        "main_texts": ocr_data["main_texts"],
        "aux_texts": ocr_data["aux_texts"],
        "combined_text": "",
        "errors": [],
        "usage": ocr_data.get("usage", {}),
    }
    
    # ✅ Node 실행 + trace
    state = _trace_with_parent("combine_texts", root_run_id, combine_texts_node, state_input)
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[ExtractFinalize] Session {session_id} deleted during execution")
        return
    
    # 최종 결과 저장
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
    
    session_repo.update_session_fields(
        session_id,
        current_step="extract_complete",
    )
    
    logger.info(f"[ExtractFinalize] ✅ Completed for session={session_id}")
    
    # 다음 단계 큐잉
    from app.services.queue_service import enqueue_pipeline_step
    enqueue_pipeline_step(
        session_id=session_id,
        channel_id=channel_id,
        step="script",
        options=options,
    )


def run_script_step(session_id, channel_id, options, storage, session_repo):
    """2단계: 스크립트 생성"""
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Script] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Script] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    # ✅ Root run ID 조회
    root_run_id = _get_root_run_id(storage, storage_prefix)
    
    session_repo.update_session_fields(session_id, current_step="generate_script")
    
    # 이전 단계 결과 로드
    extracted_key = f"{storage_prefix}pipeline/extracted_data.json"
    extracted_data = storage.download_json(extracted_key)
    
    from app.langgraph_pipeline.podcast.graph import generate_script_node
    
    # Vertex AI 설정
    project_id = os.getenv("VERTEX_AI_PROJECT_ID")
    region = os.getenv("VERTEX_AI_REGION")
    sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")
    
    state_input = {
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
    
    # ✅ Node 실행 + trace
    state = _trace_with_parent("generate_script", root_run_id, generate_script_node, state_input)
    
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


def run_audio_step(session_id, channel_id, options, storage, session_repo):
    """3단계: 오디오 생성"""
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Audio] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Audio] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    # ✅ Root run ID 조회
    root_run_id = _get_root_run_id(storage, storage_prefix)
    
    session_repo.update_session_fields(session_id, current_step="generate_audio")
    
    # 이전 단계 결과 로드
    script_key = f"{storage_prefix}pipeline/script.json"
    script_data = storage.download_json(script_key)
    
    from app.langgraph_pipeline.podcast.graph import generate_audio_node
    
    state_input = {
        "script": script_data["script"],
        "host_name": options.get("host1", "Fenrir"),
        "guest_name": options.get("host2", ""),
        "usage": script_data.get("usage", {}),
        "errors": [],
    }
    
    # ✅ Node 실행 + trace
    state = _trace_with_parent("generate_audio", root_run_id, generate_audio_node, state_input)
    
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


def run_finalize_step(session_id, channel_id, options, storage, session_repo):
    """4단계: 최종 병합 + 트랜스크립트"""
    import tempfile
    from app.utils.session_helpers import session_exists
    
    logger.info(f"[Finalize] Starting for session={session_id}")
    
    if not session_exists(session_repo, session_id):
        logger.info(f"[Finalize] Session {session_id} deleted - skipping")
        return
    
    session = session_repo.get_session(session_id)
    storage_prefix = session.get("storage_prefix", "")
    
    # ✅ Root run ID 조회
    root_run_id = _get_root_run_id(storage, storage_prefix)
    
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
        
        from app.langgraph_pipeline.podcast.graph import merge_audio_node, generate_transcript_node
        
        # ✅ Merge node
        merge_input = {
            "wav_files": temp_wav_files,
            "audio_metadata": audio_data["audio_metadata"],
            "script": script_data["script"],
            "title": script_data["title"],
            "usage": audio_data.get("usage", {}),
            "errors": [],
        }
        
        state = _trace_with_parent("merge_audio", root_run_id, merge_audio_node, merge_input)
        
        if not session_exists(session_repo, session_id):
            logger.info(f"[Finalize] Session {session_id} deleted during merge")
            return
        
        if state.get("errors"):
            raise Exception(f"Audio merge failed: {state['errors']}")
        
        session_repo.update_session_fields(session_id, current_step="merge_complete")
        
        # ✅ Transcript node
        state = _trace_with_parent("generate_transcript", root_run_id, generate_transcript_node, state)
        
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
        from pathlib import Path

        ffmpeg_path, ffprobe_path = prepare_ffmpeg_binaries()

        # pydub이 ffmpeg는 converter로 사용
        AudioSegment.converter = ffmpeg_path

        # ffprobe는 PATH에서 찾는 경우가 많아서 /tmp/bin을 PATH에 추가
        tmp_bin = str(Path(ffprobe_path).parent)  # "/tmp/bin"
        os.environ["PATH"] = tmp_bin + ":" + os.environ.get("PATH", "")

        # (있으면) pydub에 ffprobe 경로도 직접 지정
        try:
            AudioSegment.ffprobe = ffprobe_path
        except Exception:
            pass

        # (보조) env도 같이 넣어두면 다른 코드 경로에도 안전
        os.environ["FFMPEG_BINARY"] = ffmpeg_path
        os.environ["FFPROBE_BINARY"] = ffprobe_path

        audio = AudioSegment.from_file(final_audio_path)
        total_duration_sec = int(len(audio) / 1000)
        
        # 스크립트 텍스트 읽기
        with open(transcript_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        # 최종 업데이트
        if not session_exists(session_repo, session_id):
            logger.info(f"[Finalize] Session {session_id} deleted before final update")
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
        
        # ✅ Root run 종료
        logger.info(f"🔍 Root run ID for closing: {root_run_id}")
        if root_run_id:
            try:
                from langsmith import Client
                from datetime import datetime
                
                logger.info(f"✅ Attempting to close root run: {root_run_id}")
                ls_client = Client()
                ls_client.update_run(
                    root_run_id,
                    end_time=datetime.now(),
                    outputs={
                        "audio_key": audio_key,
                        "script_key": script_out_key,
                        "total_duration_sec": total_duration_sec,
                        "status": "completed",
                    }
                )
                logger.info(f"✅ LangSmith root run closed successfully: {root_run_id}")
            except Exception as e:
                logger.error(f"❌ Root run 종료 실패: {e}", exc_info=True)
        else:
            logger.warning("⚠️ No root_run_id found - cannot close root run")
        
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
# app/services/session_service.py
import os
import tempfile
import logging
from datetime import datetime, timedelta
from typing import Optional
from pydub import AudioSegment

from app.services.langgraph_service import run_langgraph, CancelledException
from app.utils.session_helpers import session_exists
from app.utils.error_codes import ErrorCodes

logger = logging.getLogger(__name__)

def get_audio_duration_sec(path: str) -> int:
    audio = AudioSegment.from_file(path)
    return int(len(audio) / 1000)

class SessionService:
    def __init__(self, channel_repo, session_repo, session_input_repo, storage):
        self.channel_repo = channel_repo
        self.session_repo = session_repo
        self.session_input_repo = session_input_repo
        self.storage = storage

    def delete_session(self, channel_id: str, session_id: str) -> bool:
        """세션 삭제 (기존 코드 유지)"""
        # 1. 채널 확인
        channel = self.channel_repo.get_channel(channel_id)
        if not channel:
            raise ValueError(ErrorCodes.CHANNEL_NOT_FOUND)

        # 2. 세션 확인
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(ErrorCodes.SESSION_NOT_FOUND)

        if session["channel_id"] != channel_id:
            raise ValueError(ErrorCodes.SESSION_NOT_FOUND)

        # 3. 파일 삭제
        storage_prefix = session.get("storage_prefix")
        if storage_prefix and hasattr(self.storage, "delete_prefix"):
            self.storage.delete_prefix(storage_prefix)
        else:
            # fallback: 개별 키만 삭제
            audio_key = session.get("audio_key")
            script_key = session.get("script_key")
            if audio_key:
                self.storage.delete(audio_key)
            if script_key:
                self.storage.delete(script_key)

        # 4. session_inputs 삭제
        self.session_input_repo.delete_inputs_by_session(session_id)

        # 5. 세션 삭제 (DB / memory)
        self.session_repo.delete_session(session_id)

        return True

    async def process_audiobook_generation(
        self,
        session_id: str,
        channel_id: str,
        options: dict,
    ):
        """
        세션 생성 후 백그라운드에서 실행되는 오디오북 생성 로직
        
        1. Storage에서 입력 파일 다운로드
        2. LangGraph 실행
        3. 결과 파일 Storage 업로드
        4. sessions 테이블 업데이트 (status, audio_key, title 등)
        """
        # 환경 변수 읽기
        google_project_id = os.getenv("VERTEX_AI_PROJECT_ID")
        google_region = os.getenv("VERTEX_AI_REGION")
        google_sa_file = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE")

        if not google_sa_file:
            raise RuntimeError(
                "VERTEX_AI_SERVICE_ACCOUNT_FILE 환경 변수가 설정되지 않았습니다!"
            )

        if not google_project_id or not google_region:
            raise RuntimeError(
                "VERTEX_AI_PROJECT_ID 또는 VERTEX_AI_REGION 환경 변수가 설정되지 않았습니다!"
            )

        temp_files = []

        try:
            logger.info(f"오디오북 생성 시작 (Session ID: {session_id})")
            logger.info(f"Vertex AI Config: project={google_project_id}, region={google_region}")

            # Step 1: 세션 상태 업데이트
            self.session_repo.update_session_fields(
                session_id,
                current_step="start",
                status="processing"
            )

            # Step 2: 세션 확인 (삭제되었는지 체크)
            session = self.session_repo.get_session(session_id)
            if not session_exists(self.session_repo, session_id):
                logger.info(f"Session {session_id}가 이미 삭제됨 - 작업 중단")
                return

            # Step 3: 입력 파일 조회
            inputs = self.session_input_repo.list_inputs(session_id)
            if not inputs:
                raise Exception("입력 파일이 없습니다.")

            main_sources = []
            aux_sources = []

            # Step 4: Storage에서 파일 다운로드
            for inp in inputs:
                source_path = None

                if inp.get("is_link"):
                    # 링크 URL 직접 사용
                    source_path = inp["link_url"]
                    logger.info(f"Link URL: {inp['link_url'][:80]}...")
                else:
                    # Storage에서 다운로드
                    input_key = inp["input_key"]
                    logger.info(f"Storage 다운로드: {input_key}")

                    try:
                        file_data = self.storage.download(input_key)
                        logger.info(f"다운로드 완료: {len(file_data):,} bytes")

                        # 임시 파일 생성
                        file_ext = os.path.splitext(input_key)[1] or ".tmp"
                        temp_fd, temp_path = tempfile.mkstemp(
                            suffix=file_ext, 
                            prefix=f"input_{inp['input_id']}_"
                        )

                        with os.fdopen(temp_fd, 'wb') as f:
                            f.write(file_data)

                        temp_files.append(temp_path)
                        source_path = temp_path

                        logger.info(f"임시 파일 생성: {temp_path}")

                    except Exception as download_error:
                        logger.error(f"Storage 다운로드 실패: {download_error}")
                        raise Exception(f"Storage 접근 실패 ({input_key}): {str(download_error)}")

                # main/aux 분류
                if inp["role"] == "main":
                    main_sources.append(source_path)
                    logger.info(f"✅ 주 소스로 추가: {source_path}")
                else:
                    aux_sources.append(source_path)
                    logger.info(f"🔎 보조 소스로 추가: {source_path}")

            if not main_sources:
                raise Exception("주 소스 파일이 없습니다.")

            logger.info(f"소스 준비 완료 - Main: {len(main_sources)}개, Aux: {len(aux_sources)}개")

            # Step 5: step_callback 정의
            def step_callback(step: str):
                # ✅ 삭제됐으면 step 업데이트도 스킵
                if not session_exists(self.session_repo, session_id):
                    return
                self.session_repo.update_session_fields(session_id, current_step=step)
                logger.info(f"📍 Step updated: {step}")

            # Step 6: LangGraph 실행
            try:
                result = await run_langgraph(
                    main_sources=main_sources,
                    aux_sources=aux_sources,
                    project_id=google_project_id,
                    region=google_region,
                    sa_file=google_sa_file,
                    host1=options.get("host1", "Fenrir"),
                    host2=options.get("host2", ""),
                    style=options.get("style", "explain"),
                    duration=options.get("duration", 5),
                    difficulty=options.get("difficulty", "intermediate"),
                    user_prompt=options.get("user_prompt", ""),
                    step_callback=step_callback,

                    cancel_check=lambda: not session_exists(self.session_repo, session_id),
                    thread_id=f"session_{session_id}",
                )
            except CancelledException as ce:
                logger.info(f"사용자가 session {session_id}를 취소함: {ce}")
                return

            logger.info("LangGraph 실행 완료")

            # Step 7: 결과 파일 경로
            audio_local = result["final_podcast_path"]
            script_local = result["transcript_path"]
            title_text = result.get("title") or "자동 생성된 팟캐스트"

            logger.info(f"Title: {title_text}")

            # Step 8: 세션 재확인 (삭제되었는지)
            session = self.session_repo.get_session(session_id)
            if not session:
                logger.info(f"Session {session_id}가 삭제됨 - 파일 업로드 스킵")
                return

            # Step 9: Storage에 결과 파일 업로드
            storage_prefix = session.get("storage_prefix", "")
            output_dir = f"{storage_prefix}output_files/"

            base_audio_name = os.path.basename(audio_local)
            base_script_name = os.path.basename(script_local)

            audio_key = f"{output_dir}audio/{base_audio_name}"
            script_key = f"{output_dir}script/{base_script_name}"

            with open(audio_local, "rb") as f:
                self.storage.upload_bytes(audio_key, f.read(), content_type="audio/mpeg")

            with open(script_local, "rb") as f:
                self.storage.upload_bytes(script_key, f.read(), content_type="text/plain")

            logger.info(f"Storage에 결과 파일 업로드 완료")

            # Step 10: 세션 최종 확인
            session = self.session_repo.get_session(session_id)
            if not session:
                logger.info(f"Session {session_id}가 업로드 후 삭제됨 - 파일 정리")
                try:
                    self.storage.delete(audio_key)
                    self.storage.delete(script_key)
                except:
                    pass
                return
            
            total_duration_sec = None
            try:
                if audio_local and os.path.exists(audio_local):
                    total_duration_sec = get_audio_duration_sec(audio_local)  # 초 단위로 리턴
            except Exception as e:
                logger.warning(f"오디오 길이 측정 실패: {e}")

            script_text = None
            try:
                if script_local and os.path.exists(script_local):
                    with open(script_local, "r", encoding="utf-8") as f:
                        script_text = f.read()
            except Exception as e:
                logger.warning(f"Transcript 파일 읽기 실패: {e}")
                # fallback: langgraph 결과에 script 키가 있으면 거기서라도
                script_text = result.get("script") or None

            # Step 11: 세션 업데이트 (완료)
            self.session_repo.update_session_fields(
                session_id,
                title=title_text,
                status="completed",
                audio_key=audio_key,
                script_key=script_key,
                script_text=script_text,                 
                total_duration_sec=total_duration_sec,
                current_step="completed",
            )

            logger.info(f"오디오북 생성 완료 (Session ID: {session_id})")

        except CancelledException:
            logger.info(f"Session {session_id} 취소됨 - 정상 종료")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"오디오북 생성 실패: {error_msg}", exc_info=True)

            # 에러 상태 업데이트
            session = self.session_repo.get_session(session_id)
            if session:
                try:
                    self.session_repo.update_session_fields(
                        session_id,
                        status="failed",
                        error_message=error_msg[:500],
                        current_step="error"
                    )
                except Exception as update_err:
                    logger.error(f"상태 업데이트 실패: {update_err}")
            else:
                logger.warning(f"Session {session_id}가 이미 삭제되어 오류 상태 업데이트 스킵")

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.info(f"임시 파일 삭제: {temp_file}")
                except Exception as cleanup_error:
                    logger.error(f"임시 파일 삭제 실패: {temp_file} - {cleanup_error}")
            logger.info("임시 파일 정리 완료")
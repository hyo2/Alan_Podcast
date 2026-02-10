# app/services/langgraph_service.py
import os
import logging
from typing import List, Dict, Any, Callable, Optional
from langsmith import traceable
from app.langgraph_pipeline.podcast.graph import create_podcast_graph
from app.langgraph_pipeline.podcast.state import PodcastState

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")
logger = logging.getLogger(__name__)


class CancelledException(Exception):
    """세션이 삭제되어 작업이 종료된 경우"""
    pass

@traceable(
    run_type="chain",
    project_name="ai-audiobook-dev",
    metadata=lambda **kwargs: {
        "session_id": kwargs.get("session_id"),
    },
)

async def run_langgraph(
    main_sources: List[str],
    aux_sources: List[str],
    project_id: str,
    region: str,
    sa_file: str,
    host1: str,
    host2: str,
    style: str = "explain",
    duration: int = 5,
    difficulty: str = "intermediate",
    user_prompt: str = "",
    step_callback: Optional[Callable[[str], None]] = None,
    session_id: Optional[str] = None,

    # 삭제/취소 여부 판단 함수
    cancel_check: Optional[Callable[[], bool]] = None,

    # thread_id 커스터마이즈 (세션/아웃풋 모두 식별 가능)
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    graph = create_podcast_graph()

    initial_state: PodcastState = {
        "main_sources": main_sources,
        "aux_sources": aux_sources,
        "source_data": {},
        "main_texts": [],
        "aux_texts": [],
        "combined_text": "",
        "title": "",
        "script": "",
        "audio_metadata": [],
        "wav_files": [],
        "final_podcast_path": "",
        "transcript_path": "",
        "errors": [],
        "current_step": "start",
        "project_id": project_id,
        "region": region,
        "sa_file": sa_file,
        "host_name": host1,
        "guest_name": host2,
        "style": style,
        "duration": duration,
        "difficulty": difficulty,
        "user_prompt": user_prompt,
    }

    def _check_cancel(where: str):
        if cancel_check and cancel_check():
            logger.info(f"⚠️ Cancelled at {where}")
            raise CancelledException(f"Cancelled at {where}")

    logger.info("🚀 Podcast LangGraph 실행 시작")

    _check_cancel("before execution")

    config = {
        "configurable": {"thread_id": thread_id or f"session_{session_id}"},
        "metadata": {
            "session_id": session_id,
            "style": style,
            "duration": duration,
        },
        "tags": [f"session-{session_id}", f"duration-{duration}min"],
    }
    
    last_step = "start"
    final_state = None

    async for event in graph.astream(initial_state, config=config):
        for _, node_state in event.items():
            _check_cancel("during execution")

            final_state = node_state
            current_step = node_state.get("current_step", last_step)

            if current_step != last_step and step_callback:
                step_callback(current_step)
                last_step = current_step
                logger.info(f"📍 Step updated: {current_step}")

    if not final_state:
        raise RuntimeError("LangGraph 실행 중 상태를 받지 못했습니다.")

    _check_cancel("before completion")

    if final_state.get("errors"):
        logger.warning(f"LangGraph errors: {final_state['errors']}")

    if not final_state.get("final_podcast_path"):
        raise RuntimeError(f"Podcast generation failed: {final_state.get('errors')}")

    return {
        "source_data": final_state["source_data"],
        "final_podcast_path": final_state["final_podcast_path"],
        "transcript_path": final_state.get("transcript_path", ""),
        "script": final_state.get("script", ""),
        "title": final_state.get("title", ""),
        "errors": final_state.get("errors", []),
    }

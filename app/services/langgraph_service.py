# app/services/langgraph_service.py
import os
import logging
from app.langgraph_pipeline.graph import create_full_graph
from app.langgraph_pipeline.state import PipelineState

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")
logger = logging.getLogger(__name__)

async def run_langgraph(
    sources: list[str],
    project_id: str,
    region: str,
    sa_file: str,
    host1: str,
    host2: str,
    style: str = "explain",
):
    """
    LangGraph 전체 파이프라인 실행
    Return: FastAPI에서 DB 저장에 필요한 모든 최종 데이터
    """

    graph = create_full_graph()

    initial_state: PipelineState = {
        "sources": sources,
        "project_id": project_id,
        "region": region,
        "sa_file": sa_file,
        "host_name": host1,
        "guest_name": host2,
        "style": style,
        "errors": [],
    }

    logger.info("🚀 LangGraph 파이프라인 실행 시작")

    final_state = graph.invoke(initial_state)

    # ------------------------------------------------------------
    # FastAPI → supabase DB에 넣을 최종 결과물을 리턴하도록 정리
    # ------------------------------------------------------------
    return {
        "final_podcast_path": final_state.get("final_podcast_path"),
        "transcript_path": final_state.get("transcript_path"),
        "script_text": final_state.get("script_text"),
        "scenes": final_state.get("scenes"),
        "metadata": final_state.get("metadata"),
        "image_plans": final_state.get("image_plans"),
        "image_prompts": final_state.get("image_prompts"),
        "timeline": final_state.get("timeline"),
        "image_paths": final_state.get("image_paths"),
        "host_name": final_state.get("host_name", host1),
        "guest_name": final_state.get("guest_name", host2),
        "errors": final_state.get("errors", []),
    }

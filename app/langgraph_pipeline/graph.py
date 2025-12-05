# app/langgraph_pipeline/graph.py
import logging
from langgraph.graph import StateGraph, END
from .state import PipelineState

# Podcast nodes
from app.langgraph_pipeline.podcast.orchestrator import (
    extract_texts_node,
    combine_texts_node,
    generate_script_node,
    generate_audio_node,
    merge_audio_node,
    generate_transcript_node,
)

# Vision nodes
from app.langgraph_pipeline.vision.script_parser_node import ScriptParserNode
from app.langgraph_pipeline.vision.metadata_extraction_node import MetadataExtractionNode
from app.langgraph_pipeline.vision.image_planning_node import ImagePlanningNode
from app.langgraph_pipeline.vision.prompt_generation_node import PromptGenerationNode
from app.langgraph_pipeline.vision.timestamp_mapper import TimestampMapper
from app.langgraph_pipeline.vision.image_generation_node import ImageGenerationNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Wrapper nodes (LangGraph 1.x는 함수형 runnable을 권장)
# ---------------------------------------------------------------------

def read_transcript_node(state: PipelineState):
    """transcript_path → script_text"""
    path = state.get("transcript_path")
    if not path:
        return {"errors": state.get("errors", []) + ["No transcript_path"]}

    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        return {"script_text": txt}
    except Exception as e:
        return {"errors": state.get("errors", []) + [str(e)]}


def script_parser_node(state):
    parser = ScriptParserNode()
    scenes = parser.parse_from_text(state["script_text"])
    return {"scenes": scenes}


def metadata_node(state: PipelineState):
    node = MetadataExtractionNode(
        project_id=state["project_id"],
        location=state["region"]
    )

    # MetadataExtractionNode는 dict 형태의 state를 받아야 함
    out = node({"scenes": state["scenes"]})
    metadata = out["metadata"]

    # dataclass 그대로 반환 (ImagePlanningNode가 변환 처리함)
    return {"metadata": metadata}


def image_planning_node(state):
    node = ImagePlanningNode(
        project_id=state["project_id"],
        location=state["region"]
    )
    out_state = node({
        "full_script": state["script_text"],
        "metadata": state["metadata"]
    })
    return {"image_plans": out_state["image_plans"]}


def prompt_generation_node(state):
    node = PromptGenerationNode(
        project_id=state["project_id"],
        location=state["region"]
    )
    out_state = node({
        "image_plans": state["image_plans"],
        "metadata": state["metadata"]
    })
    return {"image_prompts": out_state["image_prompts"]}


def timestamp_mapper_node(state):
    node = TimestampMapper()
    out = node({
        "image_prompts": state["image_prompts"]
    })
    return {"timeline": out["timeline"]}


def image_generation_node(state):
    node = ImageGenerationNode(
        project_id=state["project_id"],
        location=state["region"],
        output_dir="outputs/images"
    )
    out_state = node({"image_prompts": state["image_prompts"]})
    return {"image_paths": out_state["image_paths"]}



# ---------------------------------------------------------------------
# Create LangGraph 1.x Graph
# ---------------------------------------------------------------------
def create_full_graph():
    graph = StateGraph(PipelineState)

    # podcast nodes
    graph.add_node("extract_texts", extract_texts_node)
    graph.add_node("combine_texts", combine_texts_node)
    graph.add_node("generate_script", generate_script_node)
    graph.add_node("generate_audio", generate_audio_node)
    graph.add_node("merge_audio", merge_audio_node)
    graph.add_node("generate_transcript", generate_transcript_node)

    # bridge
    graph.add_node("read_transcript", read_transcript_node)

    # vision
    graph.add_node("parse_script", script_parser_node)
    graph.add_node("extract_metadata", metadata_node)
    graph.add_node("plan_images", image_planning_node)
    graph.add_node("generate_prompts", prompt_generation_node)
    graph.add_node("map_timestamps", timestamp_mapper_node)
    graph.add_node("generate_images", image_generation_node)

    # Flow
    graph.set_entry_point("extract_texts")

    graph.add_edge("extract_texts", "combine_texts")
    graph.add_edge("combine_texts", "generate_script")
    graph.add_edge("generate_script", "generate_audio")
    graph.add_edge("generate_audio", "merge_audio")
    graph.add_edge("merge_audio", "generate_transcript")

    graph.add_edge("generate_transcript", "read_transcript")
    graph.add_edge("read_transcript", "parse_script")
    graph.add_edge("parse_script", "extract_metadata")
    graph.add_edge("extract_metadata", "plan_images")
    graph.add_edge("plan_images", "generate_prompts")
    graph.add_edge("generate_prompts", "map_timestamps")
    graph.add_edge("map_timestamps", "generate_images")
    graph.add_edge("generate_images", END)

    return graph.compile()
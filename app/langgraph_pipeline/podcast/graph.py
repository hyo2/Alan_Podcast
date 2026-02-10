# app/langgraph_pipeline/podcast/graph.py

import logging
import json
import os
import uuid
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import PodcastState
from .metadata_generator_node import MetadataGenerator 
from .script_generator import ScriptGenerator
from .tts_service import TTSService
from .audio_processor import AudioProcessor
from .pricing import format_cost

logger = logging.getLogger(__name__)

def get_temp_output_dir() -> str:
    """환경에 맞는 임시 출력 디렉토리 반환"""
    base = os.getenv("BASE_OUTPUT_DIR", "outputs")
    return base


def extract_texts_node(state: PodcastState) -> PodcastState:
    """노드 1: MetadataGenerator를 사용하여 텍스트와 이미지 설명 추출"""
    logger.info("메타데이터 생성 및 텍스트 추출 시작...")
    
    main_sources = state.get('main_sources', [])
    aux_sources = state.get('aux_sources', [])
    
    # ✅ V4: 체크포인트 정보 추출
    session_id = state.get('session_id')
    storage_prefix = state.get('storage_prefix')
    checkpoint_callback = state.get('checkpoint_callback')
    
    if not main_sources:
        return {
            **state,
            "errors": ["처리할 주 소스 파일이 없습니다."],
            "current_step": "error"
        }

    try:
        primary_file = main_sources[0]
        supplementary_files = main_sources[1:] + aux_sources
        
        logger.info(f"Primary: {primary_file}, Supp: {len(supplementary_files)}개")

        # ✅ V4: 체크포인트 콜백 전달
        generator = MetadataGenerator(
            checkpoint_callback=checkpoint_callback,
            checkpoint_interval=5,
        )
        
        #  환경 변수 기반 경로 사용
        output_dir = get_temp_output_dir()
        temp_json_path = os.path.join(output_dir, f"temp_metadata_{uuid.uuid4().hex[:8]}.json")
        
        # ✅ V4: session_id, storage_prefix 전달
        generated_path = generator.generate(
            primary_file=primary_file,
            supplementary_files=supplementary_files,
            output_path=temp_json_path,
            session_id=session_id,
            storage_prefix=storage_prefix,
        )
        
        # ✅ Vision 토큰 정보 수집
        vision_tokens = {}
        if isinstance(generated_path, dict):
            vision_tokens = generated_path.get("vision_tokens", {})
            generated_path = generated_path.get("metadata_path", generated_path)
        
        with open(generated_path, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
            
        if os.path.exists(generated_path):
            os.remove(generated_path)
        
        main_texts = []
        aux_texts = []
        
        primary = source_data.get("primary_source", {}) 
        if primary and "content" in primary:
            text = primary["content"].get("full_text", "")
            if text:
                images = primary.get("filtered_images", [])
                if images:
                    text += "\n\n=== [VISUAL CONTEXT] (Images in the document) ===\n"
                    for img in images:
                        desc = img.get("description", "")
                        page = img.get("page_number", "?")
                        text += f"- Page {page}: {desc}\n"
                
                main_texts.append(text)

        supp_list = source_data.get("supplementary_sources", [])
        for supp in supp_list:
            text = supp.get("content", {}).get("full_text", "")
            if text:
                aux_texts.append(text)

        logger.info(f"파싱 완료 - Main: {len(main_texts)}개, Aux: {len(aux_texts)}개")
        
        # ✅ usage에 vision_tokens 저장
        current_usage = state.get("usage", {})
        if vision_tokens:
            current_usage["vision"] = vision_tokens
        
        return {
            **state,
            "source_data": source_data,
            "main_texts": main_texts,
            "aux_texts": aux_texts,
            "usage": current_usage,
            "errors": [],
            "current_step": "extract_complete"
        }

    except Exception as e:
        logger.error(f"메타데이터 생성 실패: {e}", exc_info=True)
        return {
            **state,
            "errors": state.get('errors', []) + [f"추출 오류: {str(e)}"],
            "current_step": "error"
        }


def combine_texts_node(state: PodcastState) -> PodcastState:
    """노드 2: 텍스트 구조화 및 결합"""
    logger.info("텍스트 구조화 및 결합 중...")
    
    if not state['main_texts']:
        return {
            **state,
            "errors": state.get('errors', []) + ["주 소스 텍스트가 없습니다."],
            "current_step": "error"
        }
    
    formatted_text = "=== [MAIN SOURCE] (Core Content) ===\n"
    formatted_text += "The following content is the primary topic. Focus the script on this.\n\n"
    formatted_text += "\n\n---\n\n".join(state['main_texts'])
    
    if state['aux_texts']:
        formatted_text += "\n\n\n=== [AUXILIARY SOURCE] (Reference/Context) ===\n"
        formatted_text += "Use the following content only for supporting details.\n\n"
        formatted_text += "\n\n---\n\n".join(state['aux_texts'])
    
    return {
        **state,
        "combined_text": formatted_text,
        "current_step": "combine_complete"
    }


def generate_script_node(state: PodcastState) -> PodcastState:
    """노드 3: 스크립트 생성"""
    logger.info("스크립트 생성 중...")
    try:
        from app.db.db_session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("DB session factory(SessionLocal)가 없습니다. DATABASE_URL 설정을 확인하세요.")
        db = SessionLocal()
        try:
            generator = ScriptGenerator(
                db=db,
                project_id=state['project_id'],
                region=state['region'],
                sa_file=state['sa_file'],
                style=state.get('style', 'explain')
            )
            result = generator.generate_script(
                combined_text=state['combined_text'],
                host_name=state['host_name'],
                guest_name=state['guest_name'],
                duration=state.get('duration', 5),
                difficulty=state.get('difficulty', 'intermediate'),
                user_prompt=state.get('user_prompt', "")
            )
        finally:
            db.close()
        
        new_usage = state.get("usage", {})
        if "usage" in result:
            new_usage.update(result["usage"])

        return {
            **state,
            "title": result.get("title", "Untitled"),
            "script": result.get("script", ""),
            "usage": new_usage,
            "current_step": "script_complete"
        }
    except Exception as e:
        logger.error(f"스크립트 생성 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def generate_audio_node(state: PodcastState) -> PodcastState:
    """노드 4: TTS 변환"""
    logger.info("TTS 변환 중...")
    try:
        tts = TTSService()
        metadata, files = tts.generate_audio(state['script'], state['host_name'], state['guest_name'])
        
        # ✅ TTS/STT 통계 정보 추출
        tts_stats = {}
        if metadata and len(metadata) > 0 and '_tts_stats' in metadata[0]:
            tts_stats = metadata[0].pop('_tts_stats')  # metadata에서 제거하고 state에 추가
            print(f"[DEBUG] TTS/STT stats extracted: {tts_stats}")
        else:
            print(f"[DEBUG] No _tts_stats found in metadata")
            if metadata and len(metadata) > 0:
                print(f"[DEBUG] metadata[0] keys: {metadata[0].keys()}")
        
        tts_chars = tts_stats.get('tts_characters', 0)
        stt_secs = tts_stats.get('stt_seconds', 0.0)
        print(f"[DEBUG] tts_characters={tts_chars}, stt_seconds={stt_secs}")
        
        # ✅ usage에 TTS/STT 통계 추가
        current_usage = state.get("usage", {})
        current_usage["tts_characters"] = tts_chars
        current_usage["stt_seconds"] = stt_secs
        
        new_state = {
            **state, 
            "audio_metadata": metadata, 
            "wav_files": files, 
            "current_step": "audio_complete",
            "usage": current_usage  # ✅ 업데이트된 usage
        }
        
        print(f"[DEBUG] Returning state with usage={new_state.get('usage')}")
        
        return new_state
    except Exception as e:
        logger.error(f"TTS 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def merge_audio_node(state: PodcastState) -> PodcastState:
    """노드 5: 오디오 병합"""
    logger.info("오디오 병합 중...")
    if not state.get('wav_files'):
         return {**state, "errors": state.get('errors', []) + ["오디오 파일 없음"], "current_step": "error"}
    try:
        processor = AudioProcessor()
        path = processor.merge_audio_files(state['wav_files'])
        return {**state, "final_podcast_path": path, "current_step": "merge_complete"}
    except Exception as e:
        logger.error(f"병합 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def generate_transcript_node(state: PodcastState) -> PodcastState:
    """노드 6: 트랜스크립트 생성"""
    logger.info("트랜스크립트 생성 중...")
    try:
        processor = AudioProcessor()
        path = processor.generate_transcript(state['audio_metadata'], state['final_podcast_path'])
        
        # ✅ 최종 토큰 사용량 집계 출력
        usage = state.get("usage", {})
        
        print("\n" + "="*60)
        print("🎉 팟캐스트 생성 완료!")
        print("="*60)
        
        if usage:
            from .pricing import calculate_llm_cost, calculate_vision_cost, get_pricing
            
            print("\n" + "="*60)
            print("💰 최종 비용 요약")
            print("="*60)
            print("\n📊 항목별 상세:\n")
            
            total_cost_usd = 0.0
            pricing = get_pricing()
            
            # ====================================
            # LLM (스크립트 생성)
            # ====================================
            llm_usage = usage.get("script_generation", {})
            if llm_usage:
                attempts = llm_usage.get('attempts', 0)
                attempts_detail = llm_usage.get('attempts_detail', [])
                total_input = llm_usage.get('input_tokens', 0)
                total_output = llm_usage.get('output_tokens', 0)
                
                print(f"💬 LLM (스크립트 생성) - {attempts}회 시도")
                
                # Input 상세
                if attempts_detail:
                    input_parts = []
                    input_costs = []
                    for detail in attempts_detail:
                        attempt_num = detail['attempt']
                        input_tok = detail['input_tokens']
                        input_parts.append(f"{input_tok:,} ({attempt_num}차)")
                        input_cost = input_tok * pricing['llm_input']
                        input_costs.append(f"${input_cost:.4f}")
                    
                    print(f"   Input:  " + " + ".join(input_parts) + f" = {total_input:,} tokens")
                    print(f"          " + "   + ".join(input_costs) + f" = ${sum([d['input_tokens'] * pricing['llm_input'] for d in attempts_detail]):.4f}")
                    print()
                    
                    # Output 상세
                    output_parts = []
                    output_costs = []
                    for detail in attempts_detail:
                        attempt_num = detail['attempt']
                        output_tok = detail['output_tokens']
                        output_parts.append(f"{output_tok:,} ({attempt_num}차)")
                        output_cost = output_tok * pricing['llm_output']
                        output_costs.append(f"${output_cost:.4f}")
                    
                    print(f"   Output: " + " + ".join(output_parts) + f" = {total_output:,} tokens")
                    print(f"          " + "   + ".join(output_costs) + f" = ${sum([d['output_tokens'] * pricing['llm_output'] for d in attempts_detail]):.4f}")
                else:
                    # attempts_detail 없으면 기존 방식
                    print(f"   Input:  {total_input:,} tokens (${total_input * pricing['llm_input']:.4f})")
                    print(f"   Output: {total_output:,} tokens (${total_output * pricing['llm_output']:.4f})")
                
                llm_cost = calculate_llm_cost(total_input, total_output)
                total_cost_usd += llm_cost
                print(f"\n   소계: {format_cost(llm_cost)}")
                print()
            
            # ====================================
            # Vision (이미지 필터링 + 이미지 설명 생성)
            # ====================================
            vision_usage = usage.get("vision", {})
            if vision_usage:
                keyword_tokens = vision_usage.get("keyword_extraction", 0)
                image_tokens = vision_usage.get("image_filtering", 0)
                description_tokens = vision_usage.get("image_description", 0)  # ✅ 이미지 설명
                vision_total = vision_usage.get("total", 0)
                vision_cost = vision_usage.get('cost_usd', 0.0)
                total_cost_usd += vision_cost
                
                print(f"👁️  Vision (이미지 처리)")
                print(f"   키워드 추출: {keyword_tokens:,} tokens (${keyword_tokens * pricing['vision']:.4f})")
                # ✅ 이미지 개수 표시
                images_analyzed = vision_usage.get("images_analyzed", 0)
                if images_analyzed > 0:
                    print(f"   이미지 분석:  {image_tokens:,} tokens ({images_analyzed}개 이미지) (${image_tokens * pricing['vision']:.4f})")
                else:
                    print(f"   이미지 분석:  {image_tokens:,} tokens (${image_tokens * pricing['vision']:.4f})")
                # ✅ 이미지 설명 생성 토큰 출력
                if description_tokens > 0:
                    description_count = vision_usage.get("description_count", 0)
                    print(f"   이미지 설명:  {description_tokens:,} tokens (${description_tokens * pricing['vision']:.4f}) - {description_count}개")
                print(f"\n   소계: {format_cost(vision_cost)}")
                print()
            
            # ====================================
            # TTS / STT (usage에서 가져오기)
            # ====================================
            tts_chars = usage.get('tts_characters', 0)
            stt_seconds = usage.get('stt_seconds', 0.0)
            
            if tts_chars > 0 or stt_seconds > 0:
                from .pricing import calculate_tts_cost, calculate_stt_cost
                
                if tts_chars > 0:
                    tts_cost = calculate_tts_cost(tts_chars)
                    total_cost_usd += tts_cost
                    print(f"🎙️  TTS (음성 합성)")
                    print(f"   문자: {tts_chars:,}자")
                    print(f"\n   소계: {format_cost(tts_cost)}")
                    print()
                
                if stt_seconds > 0:
                    stt_cost = calculate_stt_cost(stt_seconds)
                    total_cost_usd += stt_cost
                    print(f"🎧 STT (음성 인식)")
                    print(f"   시간: {stt_seconds:.2f}초")
                    print(f"\n   소계: {format_cost(stt_cost)}")
                    print()
            else:
                print(f"⚠️  TTS/STT 비용 정보가 state에 없습니다.")
                print(f"   tail_focus_v5_fixed.py의 성능 측정 섹션을 참고하세요.")
                print()
            
            # ====================================
            # 총합
            # ====================================
            print("="*60)
            print(f"💵 총 비용: {format_cost(total_cost_usd)}")
            print("="*60)
            
        print()
        
        return {**state, "transcript_path": path, "current_step": "complete"}
    except Exception as e:
        logger.error(f"트랜스크립트 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}

def _should_end(state: PodcastState) -> bool:
    # errors가 있거나 current_step이 error면 즉시 중단
    if state.get("current_step") == "error":
        return True
    errs = state.get("errors") or []
    return len(errs) > 0


def _route_after_extract(state: PodcastState):
    return END if _should_end(state) else "combine_texts"


def _route_after_combine(state: PodcastState):
    return END if _should_end(state) else "generate_script"


def _route_after_script(state: PodcastState):
    return END if _should_end(state) else "generate_audio"


def _route_after_audio(state: PodcastState):
    return END if _should_end(state) else "merge_audio"


def _route_after_merge(state: PodcastState):
    return END if _should_end(state) else "generate_transcript"


def _route_after_transcript(state: PodcastState):
    return END  # 마지막은 무조건 종료


def create_podcast_graph():
    """LangGraph 그래프 정의 (에러 발생 시 즉시 종료)"""
    workflow = StateGraph(PodcastState)

    workflow.add_node("extract_texts", extract_texts_node)
    workflow.add_node("combine_texts", combine_texts_node)
    workflow.add_node("generate_script", generate_script_node)
    workflow.add_node("generate_audio", generate_audio_node)
    workflow.add_node("merge_audio", merge_audio_node)
    workflow.add_node("generate_transcript", generate_transcript_node)

    workflow.set_entry_point("extract_texts")

    # 단계별 conditional routing
    workflow.add_conditional_edges("extract_texts", _route_after_extract)
    workflow.add_conditional_edges("combine_texts", _route_after_combine)
    workflow.add_conditional_edges("generate_script", _route_after_script)
    workflow.add_conditional_edges("generate_audio", _route_after_audio)
    workflow.add_conditional_edges("merge_audio", _route_after_merge)
    workflow.add_conditional_edges("generate_transcript", _route_after_transcript)

    return workflow.compile(checkpointer=MemorySaver())


def run_podcast_generation(
    main_sources: List[str],       
    aux_sources: List[str],        
    project_id: str,
    region: str,
    sa_file: str,
    host_name: str = None,
    guest_name: str = None,
    style: str = "explain",
    duration: int = 5,
    difficulty: str = "intermediate",
    user_prompt: str = ""
) -> Dict[str, Any]:
    """팟캐스트 생성 메인 실행 함수"""
    if not project_id:
        raise ValueError("Google Cloud Project ID를 지정해야 합니다")

    host = host_name if host_name else "진행자"
    guest = guest_name if guest_name else "게스트"

    logger.info(f"진행자: {host}, 게스트: {guest}")
    logger.info(f"설정 - 스타일: {style}, 시간: {duration}분, 난이도: {difficulty}")

    initial_state = {
        "main_sources": main_sources,
        "aux_sources": aux_sources,
        "source_data": {}, 
        "main_texts": [],
        "aux_texts": [],
        "combined_text": "",
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
        "host_name": host,
        "guest_name": guest,
        "style": style,
        "duration": duration,
        "difficulty": difficulty,
        "user_prompt": user_prompt
    }

    app = create_podcast_graph()
    config = {"configurable": {"thread_id": f"podcast_generation_{id(initial_state)}"}}

    logger.info("LangGraph 워크플로우 시작...")

    try:
        final_state = app.invoke(initial_state, config)
        
        if final_state.get('errors'):
            logger.warning(f"오류 발생: {final_state['errors']}")
        
        if final_state.get('final_podcast_path'):
            return {
                "final_podcast_path": final_state['final_podcast_path'],
                "transcript_path": final_state.get('transcript_path', ''),
                "errors": final_state.get('errors', []),
                "host_name": host,
                "guest_name": guest
            }
        else:
            raise RuntimeError(f"실패: {final_state.get('errors')}")
            
    except Exception as e:
        logger.error(f"실행 오류: {e}", exc_info=True)
        raise
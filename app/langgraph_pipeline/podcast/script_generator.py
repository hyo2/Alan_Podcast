# app/langgraph_pipeline/podcast/script_generator.py
import os
import re
import logging

from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

from .script.parsing import extract_json_from_llm, extract_title_fallback
from .script.cleanup import clean_script
from .script.validation import is_script_truncated, measure
from .script.prompt_builder import create_prompt
from .script.options_parser import parse_user_prompt_overrides, apply_overrides
from .script.compression import compress_script_once
from .script.postprocess import hard_cap_fallback, continue_script_fallback, expand_script_fallback, expand_middle_content
from .script.structure_analyzer import analyze_script_structure
from .utils import target_char_budget
from .pricing import calculate_llm_cost, format_cost

from sqlalchemy.orm import Session
from .prompt_service import PromptTemplateService
 
logger = logging.getLogger(__name__)

def get_tolerance_ratios(budget: int, duration_min: float) -> tuple:
    """
    duration별 절대 시간(±1분) 기반 tolerance ratio 계산
    
    목표:
    - 5분:  ±45초 허용
    - 10분: ±45초 허용
    - 15분: ±60초 허용
    
    Returns:
        (min_ratio, max_ratio): budget 대비 비율
    """
    chars_per_sec = 470 / 60  # 실제 발화 속도 기준 (7.83자/초)
    
    if duration_min <= 7:
        # 5분: ±45초
        tolerance_chars = int(45 * chars_per_sec)  # ±352자
    elif duration_min <= 12:
        # 10분: ±45초
        tolerance_chars = int(45 * chars_per_sec)  # ±352자
    else:
        # 15분 이상: ±60초
        tolerance_chars = int(60 * chars_per_sec)  # ±470자
    
    min_chars = budget - tolerance_chars
    max_chars = budget + tolerance_chars
    
    min_ratio = min_chars / budget
    max_ratio = max_chars / budget
    
    return min_ratio, max_ratio

def _build_structured_padding_prompt(is_dialogue: bool, min_add_chars: int, speaker_b_label: str = "학생") -> str:
    """
    분량이 크게 부족할 때, 길이를 안정적으로 채우기 위한 '구조화 패딩' 프롬프트.
    - 단순 이어쓰기보다 훨씬 재현성이 높음
    """
    min_add_chars = max(400, int(min_add_chars))
    
    # ============================================================
    # ✅ 마크업 금지 규칙 (공통)
    # ============================================================
    markup_rules = """
**CRITICAL - 마크업 금지:**
❌ 절대 사용 금지: (MAIN-PAGE X), (PAGE X), (VISUAL CONTEXT: ...), (IMG X) 등
✅ 대신 사용: "화면에 보이는", "슬라이드", "교재 X페이지" 등 자연스러운 표현
"""
    
    if is_dialogue:
        return f"""
너는 대화형 수업 팟캐스트 스크립트 작가다.
아래 스크립트 뒤에 자연스럽게 이어서, 분량을 채우는 **추가 대화**를 작성하라.

필수 구성(순서대로):
1) 「선생님」 3줄 요약
2) 「{speaker_b_label}」 요약 기반 질문 2개(서로 다른 포인트)
3) 「선생님」 답변 + 예시 2개(현실/학교 사례)
4) 퀴즈 3개(OX/객관식) → 「{speaker_b_label}」 답 → 「선생님」 해설
5) 적용 활동 1개 제안
6) 마무리(다음 시간 예고 + 인사) — 인사는 1회만

{markup_rules}

규칙:
- 화자 태그는 반드시 「선생님」: / 「{speaker_b_label}」: 만 사용
- 중복 감사/인사 금지(인사 1회)
- 최소 {min_add_chars}자 이상 추가

추가 스크립트만 출력해라.
""".strip()
    else:
        return f"""
너는 강의형(선생님 단독) 수업 팟캐스트 원고 작가다.
아래 원고 뒤에 자연스럽게 이어서, 분량을 채우는 **추가 강의**를 작성하라.

필수 구성(순서대로):
1) 3줄 요약
2) 핵심 개념 5개 정의
3) 적용 예시 2개
4) 퀴즈 3개(OX/객관식) + 해설
5) 적용 활동 1개
6) 마무리(다음 시간 예고 + 인사) — 인사는 1회만

{markup_rules}

규칙:
- 최소 {min_add_chars}자 이상 추가
- 끝 문장은 완결형으로 마무리

추가 원고만 출력해라.
""".strip()

def _enforce_length_with_retries(
    *,
    model,
    base_prompt: str,
    extract_text_fn,
    measure_fn,
    min_chars: int,
    max_chars: int,
    max_tries: int = 3,
    max_output_tokens: int = 4096,
) -> str:
    """
    LLM 출력이 [min_chars, max_chars] 범위를 만족할 때까지 재시도.
    - 실패하더라도 마지막 결과를 반환(상위 로직에서 추가 처리)
    """
    last_text = ""
    for i in range(max_tries):
        prompt = base_prompt
        if i > 0:
            prompt += (
                f"\n\n[피드백] 직전 출력이 길이 범위를 벗어났습니다. "
                f"반드시 {min_chars}~{max_chars}자 범위로 다시 작성하세요."
            )
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_output_tokens, "temperature": 0.2 if i > 0 else 0.3},
        )
        text = (extract_text_fn(resp) or "").strip()
        last_text = text
        n = measure_fn(text) if text else 0
        if min_chars <= n <= max_chars:
            return text
    return last_text


def _generate_with_retry(
    *,
    model,
    combined_text: str,
    host_name: str,
    guest_name: str,
    duration_min: float,
    difficulty: str,
    user_prompt: str,
    budget: int,
    style: str,
    user_prompt_template: str,
    speaker_a_label: str,
    speaker_b_label: str,
    extract_text_fn,
    max_attempts: int = 4,
    target_min_ratio: float = 0.85,
    target_max_ratio: float = 1.2,
    max_output_tokens: int = 8192,
) -> tuple:
    """재생성 기반 길이 조정
    
    Returns:
        tuple: (title, script_text, candidates_history, usage_metadata)
    """
    import time
    
    
    # ✅ 토큰 사용량 추적
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    attempts_detail = []  # ✅ 시도별 상세 내역
    
    candidates = []
    
    for attempt in range(1, max_attempts + 1):
        # 재생성 정보 구성
        if attempt == 1:
            retry_info = None
            logger.info(f"[1차 생성 시작] 목표: {budget}자")
        else:
            # ✅ candidates가 비어있으면 재시도 정보 없이 진행
            if not candidates:
                retry_info = None
                logger.warning(f"[{attempt}차 시작] 이전 시도 모두 실패 - 재시도 정보 없이 진행")
            else:
                prev_script, prev_ratio, _ = candidates[-1]
                prev_len = measure(prev_script)
                
                if prev_ratio > target_max_ratio:
                    status = 'TOO_LONG'
                elif prev_ratio < target_min_ratio:
                    status = 'TOO_SHORT'
                else:
                    status = 'IN_RANGE'
                
                retry_info = {
                    'attempt': attempt,
                    'prev_len': prev_len,
                    'prev_ratio': prev_ratio,
                    'status': status,
                }
                
                logger.info(
                    f"[{attempt}차 재생성 시작] 이전: {prev_len}자 ({prev_ratio:.1%}), "
                    f"상태: {status}"
                )
        
        # 프롬프트 생성
        prompt = create_prompt(
            combined_text=combined_text,
            host_name=host_name,
            guest_name=guest_name,
            duration=duration_min,
            difficulty=difficulty,
            user_prompt=user_prompt,
            budget=budget,
            style=style,
            user_prompt_template=user_prompt_template,
            speaker_a_label=speaker_a_label,
            speaker_b_label=speaker_b_label,
            retry_info=retry_info,
        )
        
        # ============================================================
        # ✅ 마크업 금지 규칙 추가 (TTS 부자연스러움 방지)
        # ============================================================
        markup_prevention = """

**CRITICAL - 형식 규칙 (매우 중요!):**
"""
        
        if style == "lecture":
            markup_prevention += """
1. ✅ 각 발화마다 반드시 「선생님」: 태그로 시작
2. ✅ 모든 줄은 「선생님」: 로 시작해야 합니다
3. ✅ 한 발화는 100-300자로 제한
4. ❌ 줄바꿈만으로 발화를 구분하지 마세요
"""
        else:
            markup_prevention += f"""
1. ✅ 각 발화마다 반드시 화자 태그로 시작
2. ✅ 「선생님」: 또는 「{speaker_b_label}」:
3. ✅ 한 발화는 100-300자로 제한
4. ❌ 줄바꿈만으로 발화를 구분하지 마세요
"""
        
        markup_prevention += """

**CRITICAL - 마크업 금지 (매우 중요!):**
❌ 절대 사용 금지: (MAIN-PAGE X), (PAGE X), (VISUAL CONTEXT: ...), (IMG X), (Figure X), (표 X), (그림 X) 등 괄호 안의 메타데이터
✅ 대신 사용: "화면에 보이는", "슬라이드", "교재 X페이지", "표를 보면" 등 자연스러운 표현

**이유:** 괄호 안의 마크업은 TTS가 "메인 페이지 투", "비주얼 컨텍스트" 등으로 읽어서 오디오가 부자연스럽습니다.

**올바른 예시:**
✅ 좋음: "음운은 중요합니다"
✅ 좋음: "교재 2페이지에 나온 것처럼, 음운은 중요합니다"
✅ 좋음: "화면에 보이는 발음 기관 그림처럼, 자음은..."
✅ 좋음: "슬라이드의 표를 보시면 자음 체계를 한눈에 알 수 있습니다"

**잘못된 예시 (절대 금지):**
❌ 나쁨: "음운은 (MAIN-PAGE 2) 중요합니다"
❌ 나쁨: "(VISUAL CONTEXT: 발음 기관) 자음은..."
❌ 나쁨: "자, 이제 (PAGE 5) 넘어가봅시다"
"""

        if style == "lecture":
            markup_prevention += """
❌ 나쁨: 「선생님」: 안녕하세요!
        오늘은 음운에...  ← 태그 없음 (금지!)
"""
        
        markup_prevention += """

**참고:** 시청각 자료 언급은 자유롭게 하되, 괄호 마크업만 사용하지 마세요.
"""
        
        prompt += markup_prevention
        
        # LLM 호출
        generation_config = {
            "max_output_tokens": max_output_tokens,
            "temperature": 0.7 if attempt == 1 else 0.5,
        }
        
        # ✅ 429 에러 재시도 로직 (최대 3번)
        max_retries_for_429 = 3
        for retry_429 in range(max_retries_for_429):
            try:
                response = model.generate_content(prompt, generation_config=generation_config)
                
                # ✅ 시도별 상세 토큰 로깅
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    
                    # 토큰 누적
                    total_input_tokens += usage.prompt_token_count
                    total_output_tokens += usage.candidates_token_count
                    total_tokens += usage.total_token_count
                    
                    # ✅ 시도별 상세 내역 저장
                    attempts_detail.append({
                        "attempt": attempt,
                        "input_tokens": usage.prompt_token_count,
                        "output_tokens": usage.candidates_token_count,
                        "total_tokens": usage.total_token_count
                    })
                    
                    # logger와 print 둘 다 사용
                    logger.info(f"📝 시도 {attempt}/{max_attempts}:")
                    logger.info(f"   Input:  {usage.prompt_token_count:,} tokens")
                    logger.info(f"   Output: {usage.candidates_token_count:,} tokens")
                    logger.info(f"   Total:  {usage.total_token_count:,} tokens")
                    
                    print(f"📝 시도 {attempt}/{max_attempts}:")
                    print(f"   Input:  {usage.prompt_token_count:,} tokens")
                    print(f"   Output: {usage.candidates_token_count:,} tokens")
                    print(f"   Total:  {usage.total_token_count:,} tokens")
                
                raw_text = extract_text_fn(response).strip()
                
                if not raw_text:
                    logger.warning(f"[{attempt}차 실패] 빈 응답")
                    break  # 429 재시도 루프 탈출, 다음 attempt로
                
                # JSON 파싱 시도
                try:
                    from .script.parsing import extract_json_from_llm
                    data = extract_json_from_llm(raw_text)
                    title = data.get("title", "제목 없음").strip()
                    script_text = data.get("script", "").strip()
                except Exception:
                    from .script.parsing import extract_title_fallback
                    title = extract_title_fallback(raw_text) or "자동 생성된 팟캐스트"
                    script_text = clean_script(raw_text)
                
                script_text = clean_script(script_text)
                
                # 길이 측정
                current_len = measure(script_text)
                ratio = current_len / budget
                
                candidates.append((script_text, ratio, title))
                
                # ✅ 상세 결과 로깅
                logger.info(f"   결과: {current_len:,}자 / 목표 {budget:,}자 ({ratio:.1%})")
                logger.info(f"   목표 범위: {target_min_ratio:.1%}~{target_max_ratio:.1%}")
                
                print(f"   결과: {current_len:,}자 / 목표 {budget:,}자 ({ratio:.1%})")
                print(f"   목표 범위: {target_min_ratio:.1%}~{target_max_ratio:.1%}")
                
                # 존치 범위 진입 시 즉시 채택
                if target_min_ratio <= ratio <= target_max_ratio:
                    logger.info(f"   ✅ 성공! 목표 범위 진입 - 즉시 채택")
                    print(f"   ✅ 성공! 목표 범위 진입 - 즉시 채택")
                    # ✅ early return도 usage_metadata 포함
                    usage_metadata = {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_tokens,
                        "attempts": attempt,
                        "attempts_detail": attempts_detail  # ✅ 시도별 상세 내역
                    }
                    
                    # 최종 요약
                    logger.info(f"\n💰 LLM 토큰 사용량 요약:")
                    logger.info(f"   총 시도: {attempt}회")
                    logger.info(f"   Input:  {total_input_tokens:,} tokens")
                    logger.info(f"   Output: {total_output_tokens:,} tokens")
                    logger.info(f"   Total:  {total_tokens:,} tokens")
                    
                    print(f"\n💰 LLM 토큰 사용량 요약:")
                    print(f"   총 시도: {attempt}회")
                    print(f"   Input:  {total_input_tokens:,} tokens")
                    print(f"   Output: {total_output_tokens:,} tokens")
                    print(f"   Total:  {total_tokens:,} tokens")
                    
                    return title, script_text, candidates, usage_metadata
                else:
                    if ratio < target_min_ratio:
                        logger.info(f"   ❌ 실패: 길이 부족 ({ratio:.1%} < {target_min_ratio:.1%})")
                        print(f"   ❌ 실패: 길이 부족 ({ratio:.1%} < {target_min_ratio:.1%})")
                    else:
                        logger.info(f"   ❌ 실패: 길이 초과 ({ratio:.1%} > {target_max_ratio:.1%})")
                        print(f"   ❌ 실패: 길이 초과 ({ratio:.1%} > {target_max_ratio:.1%})")
                
                # 성공했으면 429 재시도 루프 탈출
                break
                
            except Exception as e:
                error_str = str(e)
                
                # ✅ 429 에러 감지 및 재시도
                if ('429' in error_str or 'Resource exhausted' in error_str or 'quota' in error_str.lower()):
                    if retry_429 < max_retries_for_429 - 1:
                        wait_time = 2 ** (retry_429 + 1)  # 2, 4, 8초
                        logger.warning(
                            f"[{attempt}차-{retry_429+1}번째 429 에러] "
                            f"{wait_time}초 대기 후 재시도... ({error_str[:100]})"
                        )
                        time.sleep(wait_time)
                        continue  # 429 재시도 루프 계속
                    else:
                        logger.error(
                            f"[{attempt}차 429 에러] 최대 재시도 횟수 초과 ({max_retries_for_429}회) - "
                            f"다음 attempt로 이동"
                        )
                        break  # 429 재시도 루프 탈출, 다음 attempt로
                else:
                    # 429가 아닌 다른 에러
                    logger.error(f"[{attempt}차 오류] {e}")
                    break  # 429 재시도 루프 탈출, 다음 attempt로
    
    # 모든 시도 완료 - 최선 선택
    if not candidates:
        raise RuntimeError(
            "모든 재생성 시도 실패 - 유효한 스크립트 생성 불가\n"
            "가능한 원인:\n"
            "- API 할당량 초과 (429 에러)\n"
            "- 네트워크 문제\n"
            "- 잘못된 프롬프트 형식"
        )
    
    # 1.0에 가장 가까운 후보 선택
    best = min(candidates, key=lambda x: abs(x[1] - 1.0))
    best_script, best_ratio, best_title = best
    
    logger.warning(
        f"🔄 [최선 선택] {max_attempts}회 시도 후 1.0 최근접 선택: "
        f"{measure(best_script):,}자 ({best_ratio:.1%})"
    )
    
    # ✅ 토큰 정보 반환
    usage_metadata = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "attempts": max_attempts,
        "attempts_detail": attempts_detail  # ✅ 시도별 상세 내역
    }
    
    # 최종 요약
    logger.info(f"\n💰 LLM 토큰 사용량 요약:")
    logger.info(f"   총 시도: {max_attempts}회 (전체 시도 완료)")
    logger.info(f"   Input:  {total_input_tokens:,} tokens")
    logger.info(f"   Output: {total_output_tokens:,} tokens")
    logger.info(f"   Total:  {total_tokens:,} tokens")
    
    print(f"\n💰 LLM 토큰 사용량 요약:")
    print(f"   총 시도: {max_attempts}회 (전체 시도 완료)")
    print(f"   Input:  {total_input_tokens:,} tokens")
    print(f"   Output: {total_output_tokens:,} tokens")
    print(f"   Total:  {total_tokens:,} tokens")
    
    return best_title, best_script, candidates, usage_metadata


class ScriptGenerator:
    """LLM을 사용한 팟캐스트 스크립트 생성 (PostgreSQL + Vertex AI)"""
   
        # ✅ db Session을 생성자에서 받도록 변경
    def __init__(self, db: Session, project_id: str, region: str, sa_file: str, style: str = "explain"):
        self.project_id = project_id
        self.region = region
        self.sa_file = sa_file
        self.style = style
        self.db = db  # ✅ 전달받은 db 객체 저장
       
        self._init_vertex_ai()
        self._load_prompt_template()
   
    def _init_vertex_ai(self):
        """Vertex AI 초기화"""
        if self.sa_file and os.path.exists(self.sa_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.sa_file
            logger.info(f"인증 파일 환경변수 설정 완료: {self.sa_file}")
 
        credentials = self._load_credentials()
       
        try:
            vertexai.init(
                project=self.project_id,
                location=self.region,
                credentials=credentials
            )
            logger.info(f"Vertex AI 초기화 완료: {self.project_id} / {self.region}")
        except Exception as e:
            logger.error(f"Vertex AI 초기화 실패: {e}")
            raise
   
    def _load_credentials(self):
        """서비스 계정 인증 정보 로드"""
        if os.path.exists(self.sa_file):
            try:
                return service_account.Credentials.from_service_account_file(self.sa_file)
            except Exception as e:
                raise RuntimeError(f"서비스 계정 파일 로드 오류: {e}")
        else:
            logger.warning(f"서비스 계정 파일을 찾을 수 없습니다: {self.sa_file}")
            return None
   
    def _load_prompt_template(self):
        """프롬프트 템플릿 로드 (PostgreSQL 연동)"""
        try:
            template = PromptTemplateService.get_template(self.db, self.style)

            if template:
                self.system_prompt = template["system_prompt"]
                self.user_prompt_template = template["user_prompt_template"]
                logger.info(f"프롬프트 템플릿 로드 성공: {template['style_name']}")
            else:
                logger.warning(f"템플릿을 찾을 수 없어 기본 템플릿 사용: {self.style}")
                default_template = PromptTemplateService.get_default_template(self.db)
                self.system_prompt = default_template["system_prompt"]
                self.user_prompt_template = default_template["user_prompt_template"]

        except Exception as e:
            logger.error(f"템플릿 로드 중 오류 발생: {e}")
            self.system_prompt = "You are a teacher. Respond in Korean."
            self.user_prompt_template = "Create a dialogue in Korean:\n{combined_text}"
 
    def _extract_text_from_gemini_response(self, resp) -> str:
        """Gemini 응답에서 텍스트를 안전하게 추출"""
        if not resp or not getattr(resp, "candidates", None):
            return ""

        text = ""
        try:
            c = resp.candidates[0]
            if hasattr(c, "content") and hasattr(c.content, "parts"):
                for part in c.content.parts:
                    if getattr(part, "text", None):
                        text += part.text
        except Exception:
            return ""

        return text.strip()

    def generate_script(
        self,
        combined_text: str,
        host_name: str,
        guest_name: str,
        duration: int = 5,
        difficulty: str = "intermediate",
        user_prompt: str = ""
    ) -> dict:
        """팟캐스트 스크립트 생성"""
         # ---------------------------------------------------------------------------------
         # ✅ 안전장치: 입력 컨텍스트(강의 텍스트)가 비어있으면 스크립트 생성 금지
         # - OCR 비활성화 / 이미지 기반 PDF 등으로 실제 텍스트를 못 뽑았을 때
         # - LangSmith에서 [MAIN-PAGE ...] 마커만 있고 본문이 비는 케이스를 차단
         # ---------------------------------------------------------------------------------
        if not combined_text or not combined_text.strip():
             logger.error("[입력 텍스트 비정상] combined_text가 비어있거나 마커-only 입니다. OCR/추출 실패 가능.")
             raise ValueError(
                 "강의 텍스트(combined_text)가 비어 있어 스크립트를 생성할 수 없습니다. "
                 "이미지 기반 PDF(OCR 필요) 또는 텍스트 추출 실패 가능성이 큽니다."
             )
        
        # 페이지 마커만 있고 실제 본문이 없는 경우도 차단
         # 예: [MAIN-PAGE 1: Page 1]\n\n ... 반복
        marker_stripped = re.sub(r"\[(MAIN|SUPP\d+)-PAGE\s*\d+:[^\]]*\]", "", combined_text)
        marker_stripped = re.sub(r"===\s*\[[^\]]+\]\s*===.*?\n", "", marker_stripped)
        marker_stripped = re.sub(r"\s+", "", marker_stripped)
        if len(marker_stripped) < 30:
            logger.error("[입력 텍스트 비정상] combined_text가 비어있거나 마커-only 입니다. OCR/추출 실패 가능.")
            raise ValueError(
                "강의 텍스트가 페이지 마커만 존재하고 실제 본문이 거의 없습니다. "
                "OCR이 비활성화되어 있거나, PDF가 이미지 기반일 수 있습니다."
            )

        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.5-flash-exp")

       # ✅ user_prompt에서 override 추출 → 옵션보다 우선 적용
        duration_min = float(duration)
    
       # ✅ user_prompt에서 override 추출 → 옵션보다 우선 적용
        overrides = parse_user_prompt_overrides(user_prompt)
        duration_min, style_from_prompt, difficulty = apply_overrides(duration_min, self.style, difficulty, overrides)

        # style override가 들어오면, self.style도 이 호출에 한해 덮어쓰기(로컬 변수로)
        style = style_from_prompt or self.style

        # ✅ 대화형 여부는 style 결정 직후 확정하기 (UnboundLocalError 방지)
        is_dialogue = (style != "lecture")


        # ✅ teacher_teacher 프리셋(MVP): speaker_b_label만 교체
        dialogue_mode = overrides.get("dialogue_mode") or None
        speaker_a_label = "선생님"
        speaker_b_label = "학생"
        if is_dialogue and dialogue_mode == "teacher_teacher":
            speaker_b_label = "선생님2"
        
        logger.info(
            f"[speaker preset] overrides={overrides}, "
            f"style={style}, is_dialogue={is_dialogue}, "
            f"speaker_b_label={speaker_b_label}, "
            f"user_prompt_preview={repr((user_prompt or '')[:120])}"
        )

        # ✅ float 분을 반영해 budget 계산 (반올림/상한/하한)
        budget = target_char_budget(duration_min, style)

        logger.info(
            f"[override 적용] duration_min={duration_min:.2f}, "
            f"budget={budget}, style={style}, difficulty={difficulty}"
        )
        
        logger.info(f"모델: {model_name} / 목표: {duration_min:.2f}분 ({budget}자) / 난이도: {difficulty} / 스타일: {style}")
        model = GenerativeModel(
        model_name,
        system_instruction=self.system_prompt
        )
        
        # ===== effective_user_prompt_template 설정 =====
        effective_user_prompt_template = self.user_prompt_template
        
        # ===== max_tokens 계산 =====
        # 한글 특성 반영: 1자 ≈ 2.5-3 토큰 + JSON 구조 오버헤드 + 안전 여유
        estimated_tokens = int(budget * 3.5)

        if duration_min <= 6:          # ~5분
            max_cap = 6144
        elif duration_min <= 11:       # ~10분
            max_cap = 8192
        elif duration_min <= 16:       # ~15분
            max_cap = 12288
        else:                          # 20분 이상 등
            max_cap = 16384

        max_tokens = max(2000, min(max_cap, estimated_tokens))

        logger.info(f"[CONFIG] budget={budget}자, max_tokens={max_tokens}")
       
        try:
            # ===== 재생성 기반 스크립트 생성 =====
            # ✅ duration별 동적 tolerance 계산
            min_ratio, max_ratio = get_tolerance_ratios(budget, duration_min)
            min_chars = int(budget * min_ratio)
            max_chars = int(budget * max_ratio)
            
            logger.info("=" * 80)
            logger.info("재생성 기반 스크립트 생성 시작")
            logger.info(f"목표: {budget}자 (허용 범위: {min_chars}~{max_chars}자, ±1분 기준)")
            logger.info(f"Tolerance: {min_ratio:.1%}~{max_ratio:.1%}")
            logger.info("=" * 80)
            
            title, script_text, candidates, llm_usage = _generate_with_retry(
                model=model,
                combined_text=combined_text,
                host_name=host_name,
                guest_name=guest_name,
                duration_min=duration_min,
                difficulty=difficulty,
                user_prompt=user_prompt,
                budget=budget,
                style=style,
                user_prompt_template=effective_user_prompt_template,
                speaker_a_label=speaker_a_label,
                speaker_b_label=speaker_b_label,
                extract_text_fn=self._extract_text_from_gemini_response,
                max_attempts=4,
                target_min_ratio=min_ratio,
                target_max_ratio=max_ratio,
                max_output_tokens=max_tokens,
            )
            
            # ===== usage 메타데이터 집계 =====
            # ✅ LLM 비용 계산 (환경변수 기반)
            input_tokens = llm_usage.get('input_tokens', 0)
            output_tokens = llm_usage.get('output_tokens', 0)
            total_cost = calculate_llm_cost(input_tokens, output_tokens)
            
            # llm_usage에 cost 추가
            usage_with_cost = {**llm_usage, "cost_usd": total_cost}
            
            logger.info(f"[재생성 완료] 최종 선택: {measure(script_text)}자")
            logger.info(f"[시도 이력] 총 {len(candidates)}회 시도")
            logger.info(f"[토큰 사용] Input: {input_tokens:,}, Output: {output_tokens:,}, Total: {llm_usage.get('total_tokens', 0):,}")
            logger.info(f"[비용] {format_cost(total_cost)}")
            
            print(f"💵 LLM 비용: {format_cost(total_cost)}")
            
            # ===== 최종 검증 및 보정 (간소화) =====
            current_len = measure(script_text)
            ratio = current_len / budget
            
            logger.info("=" * 80)
            logger.info("최종 검증 시작")
            logger.info("=" * 80)
            
            # 1. 끊김 감지 → 이어쓰기
            is_incomplete, incomplete_reason = is_script_truncated(script_text)
            if is_incomplete:
                logger.warning(f"[끊김 감지] {incomplete_reason} → 이어쓰기")
                script_text = continue_script_fallback(
                    script_text=script_text,
                    budget=budget,
                    model=model,
                    style=style,
                    extract_text_fn=self._extract_text_from_gemini_response,
                    speaker_b_label=speaker_b_label,
                )
                script_text = clean_script(script_text)
                current_len = measure(script_text)
                ratio = current_len / budget
                logger.info(f"[이어쓰기 후] {current_len}자 ({ratio:.1%})")
            
            # 2. tolerance 초과 → 하드캡
            if ratio > max_ratio:  # tolerance 최대치 초과 시 하드캡
                logger.error(f"[tolerance 초과] {current_len}자 ({ratio:.1%}) > {max_chars}자 ({max_ratio:.1%}) → 하드캡")
                script_text = hard_cap_fallback(
                    script_text=script_text,
                    budget=max_chars,  # tolerance 최대치를 목표로
                    model=model,
                    style=style,
                    extract_text_fn=self._extract_text_from_gemini_response,
                    speaker_b_label=speaker_b_label,
                )
                script_text = clean_script(script_text)
                current_len = measure(script_text)
                ratio = current_len / budget
                logger.info(f"[하드캡 후] {current_len}자 ({ratio:.1%})")
            
            # ===== 최종 결과 =====
            final_len = measure(script_text)
            final_ratio = final_len / budget
            
            logger.info("=" * 80)
            logger.info(f"[최종 결과] {final_len}자 ({final_ratio:.1%})")
            logger.info(f"[제목] {title}")
            logger.info("=" * 80)
            
            # 최종 상태 로깅 (동적 tolerance 반영)
            if final_ratio < 0.6:  # 60% 미만 (극단 비정상)
                logger.error(f"⚠️ [비정상] 목표의 60% 미만: {final_len}자 / {budget}자")
            elif final_ratio < min_ratio:  # 허용 최소치 미달
                logger.warning(f"⚠️ [부족] 허용 범위 미달: {final_len}자 < {min_chars}자 (목표: {budget}자)")
            elif final_ratio > 1.5:  # 150% 초과 (극단 비정상)
                logger.warning(f"⚠️ [초과] 목표의 150% 초과: {final_len}자 / {budget}자")
            elif final_ratio > max_ratio:  # 허용 최대치 초과
                logger.warning(f"⚠️ [초과] 허용 범위 초과: {final_len}자 > {max_chars}자 (목표: {budget}자)")
            else:
                logger.info(f"✅ [정상] 목표 범위 내: {final_len}자 ({min_chars}~{max_chars}자)")
 
            # ============================================================
            # ✅ 프론트엔드 UI 노이즈 제거 (이스케이프 문자)
            # ============================================================
            # JSON 생성 시 LLM이 추가한 \ 제거
            script_text = script_text.replace('\\', '')
            title = title.replace('\\', '')
            
            return {
                "title": title,
                "script": script_text,
                "usage": {
                    "script_generation": usage_with_cost
                }
            }
           
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}", exc_info=True)
            raise RuntimeError(f"스크립트 생성 실패: {str(e)}") from e
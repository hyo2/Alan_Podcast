"""
이미지 계획 노드 (LangGraph 안정화 버전)
전체 스크립트를 분석하여 n개의 이미지 계획(JSON)을 생성
"""

import json
import os
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

# Vertex AI import
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지가 없습니다.")


# -------------------------------------------------------------------
# Dataclass 정의
# -------------------------------------------------------------------

@dataclass
class ImagePlan:
    """이미지 계획"""
    image_id: str
    title: str
    description: str
    key_concepts: List[str]
    covered_timestamps: List[str]
    primary_timestamp: str
    duration: int
    visual_concept: str


# -------------------------------------------------------------------
# JSON Normalization 함수 — 핵심
# -------------------------------------------------------------------

def normalize_json_text(raw: str) -> str:
    """
    Gemini가 생성한 JSON-like 텍스트를 완전한 JSON 문자열로 정규화
    """
    if not raw:
        raise ValueError("빈 응답입니다.")

    # 1) 코드블록 제거
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        raw = raw.replace("json", "", 1).strip()

    # 2) JSON 시작 전 텍스트 제거
    start = raw.find("{")
    if start != -1:
        raw = raw[start:]

    # 3) JSON 끝 이후 텍스트 제거
    end = raw.rfind("}")
    if end != -1:
        raw = raw[:end + 1]

    # 4) 양쪽 공백 제거
    return raw.strip()


# -------------------------------------------------------------------
# Gemini 프롬프트
# -------------------------------------------------------------------

IMAGE_PLANNING_PROMPT = """
당신은 교육 콘텐츠 비디오 제작 전문가입니다.

아래 팟캐스트 스크립트와 분석 정보를 기반으로, 핵심 개념을 설명하는 이미지 계획을 JSON으로 생성하세요.

## 전체 스크립트:
{full_script}

## 메타데이터(JSON):
{metadata}

## 팟캐스트 길이: {duration_minutes}분

### 출력 형식(JSON):
{{
  "image_plans": [
    {{
      "image_id": "img_001",
      "title": "짧은 이미지 제목",
      "description": "이미지가 설명하는 개념 요약 (2~3문장)",
      "key_concepts": ["개념1", "개념2"],
      "covered_timestamps": ["00:01:24", "00:01:30"],
      "primary_timestamp": "00:01:24",
      "duration": 20,
      "visual_concept": "시각적으로 무엇을 그릴지 구체적 묘사"
    }}
  ]
}}

### 중요:
- 반드시 순수한 JSON만 반환하세요.
- JSON 외 텍스트 금지.
"""


# -------------------------------------------------------------------
# Node 본체
# -------------------------------------------------------------------

class ImagePlanningNode:
    """
    이미지 계획 생성 LangGraph 노드
    """

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash"
    ):
        # 프로젝트 자동 탐지
        if project_id is None:
            project_id = (
                os.getenv("GOOGLE_CLOUD_PROJECT")
                or os.getenv("GCP_PROJECT")
            )

            # 서비스 계정 JSON에서도 탐지
            if not project_id:
                sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if sa_path and os.path.exists(sa_path):
                    try:
                        with open(sa_path, "r") as f:
                            project_id = json.load(f).get("project_id")
                    except:
                        pass

            if not project_id:
                print("⚠️  프로젝트 ID 자동 탐지 실패")

        self.project_id = project_id
        self.location = location
        self.model_name = model_name

        # Vertex 초기화
        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ 이미지 계획 노드 초기화: {model_name}")
            except Exception as e:
                print(f"⚠️  Vertex 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            print("⚠️  Gemini 모델 없음")

    # -------------------------------------------------------------------
    # duration 계산
    # -------------------------------------------------------------------

    def _calculate_duration(self, full_script: str) -> int:
        import re
        timestamps = re.findall(r"\[(\d{2}:\d{2}:\d{2})\]", full_script)
        if not timestamps:
            return 5
        hh, mm, ss = map(int, timestamps[-1].split(":"))
        minutes = hh * 60 + mm + (1 if ss else 0)
        return max(1, minutes)

    # -------------------------------------------------------------------
    # 핵심 메서드: 이미지 계획 생성
    # -------------------------------------------------------------------

    def create_image_plans(self, full_script: str, metadata: Any) -> List[ImagePlan]:

        if not self.model:
            raise RuntimeError("Vertex AI 모델 초기화 실패")

        duration_minutes = self._calculate_duration(full_script)

        # metadata dict 변환
        if hasattr(metadata, "__dataclass_fields__"):
            meta_dict = asdict(metadata)
        else:
            meta_dict = metadata

        # Gemini 프롬프트 생성
        prompt = IMAGE_PLANNING_PROMPT.format(
            full_script=full_script,
            metadata=json.dumps(meta_dict, ensure_ascii=False, indent=2),
            duration_minutes=duration_minutes
        )

        # LLM 호출
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json"
            }
        )

        raw = response.text.strip()

        # 🔧 JSON 정규화
        normalized = normalize_json_text(raw)

        try:
            result = json.loads(normalized)
        except Exception as e:
            print("\n❌ JSON 파싱 실패. 응답 원본 일부:")
            print(normalized[:500])
            raise RuntimeError(f"JSON Parse Error: {str(e)}")

        # image_plans 파싱
        plans_data = result.get("image_plans", [])
        plans: List[ImagePlan] = []

        for p in plans_data:
            plans.append(
                ImagePlan(
                    image_id=p["image_id"],
                    title=p["title"],
                    description=p["description"],
                    key_concepts=p["key_concepts"],
                    covered_timestamps=p["covered_timestamps"],
                    primary_timestamp=p["primary_timestamp"],
                    duration=p.get("duration", 20),
                    visual_concept=p["visual_concept"]
                )
            )

        print(f"✅ {len(plans)}개 이미지 계획 생성 완료")
        return plans

    # -------------------------------------------------------------------
    # LangGraph entry point
    # -------------------------------------------------------------------

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        full_script = state.get("full_script") or state.get("script_text")
        metadata = state.get("metadata")

        if not full_script:
            raise ValueError("full_script/script_text 없음")

        if not metadata:
            raise ValueError("metadata 없음")

        plans = self.create_image_plans(full_script, metadata)

        return {
            **state,
            "image_plans": plans
        }

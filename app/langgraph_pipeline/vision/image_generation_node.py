"""
이미지 생성 노드 (hyunsu에서 가져옴)
"""

# 원본: hyunsu/app/nodes/image_generation_node.py

import os
import time
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
from io import BytesIO

# Vertex AI
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지 없음 (pip install google-cloud-aiplatform)")


class ImageGenerationNode:
    """
    이미지 생성 노드
    (hyunsu 버전 그대로)
    """

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        output_dir: str = "outputs/images"
    ):
        if project_id is None:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if credentials_path and os.path.exists(credentials_path):
                    try:
                        with open(credentials_path, 'r') as f:
                            creds = json.load(f)
                            project_id = creds.get('project_id')
                    except Exception:
                        pass
            if not project_id:
                print("⚠️  프로젝트 ID를 찾을 수 없습니다.")

        self.project_id = project_id
        self.location = location
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel("gemini-2.5-flash-image")
                print(f"✅ 이미지 생성 노드 초기화: gemini-2.5-flash-image 🍌")
            except Exception as e:
                print(f"⚠️  초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
            if not project_id:
                print("⚠️  이미지 생성 불가 (프로젝트 ID 없음)")

    def generate_image(
        self,
        prompt: str,
        image_id: str,
        max_retries: int = 3,
        retry_delay: int = 5
    ) -> Optional[str]:
        if not self.model:
            print(f"⚠️  {image_id}: 모델 없음, 스킵")
            return None

        for attempt in range(max_retries):
            try:
                print(f"\n🎨 {image_id} 생성 중... (시도 {attempt + 1}/{max_retries})")

                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "response_modalities": ["IMAGE"],
                        "image_config": {
                            "aspect_ratio": "16:9"
                        }
                    }
                )

                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data
                        image = Image.open(BytesIO(image_data))
                        image_path = os.path.join(self.output_dir, f"{image_id}.png")
                        image.save(image_path, "PNG")
                        print(f"✅ {image_id}: 저장 완료 ({image_path})")
                        return image_path

                print(f"⚠️  {image_id}: 응답에 이미지 없음")
                return None

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "quota" in error_msg.lower() or "resource" in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"⚠️  {image_id}: 할당량 초과, {wait_time}초 대기 후 재시도...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ {image_id}: 할당량 초과, 재시도 실패")
                        return None
                print(f"❌ {image_id}: 생성 실패 - {error_msg}")
                return None

        return None

    def generate_images_from_prompts(
        self,
        prompts: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> Dict[str, str]:
        print("\n" + "="*80)
        print("🖼️  이미지 생성 시작")
        print("="*80)

        image_paths = {}

        for i, prompt_data in enumerate(prompts):
            if show_progress:
                print(f"\n[{i+1}/{len(prompts)}] {prompt_data.get('image_id', 'unknown')}")

            image_id = prompt_data.get('image_id')
            prompt = prompt_data.get('image_prompt')

            if not image_id or not prompt:
                print(f"⚠️  프롬프트 데이터 불완전, 스킵")
                continue

            image_path = self.generate_image(prompt, image_id)

            if image_path:
                image_paths[image_id] = image_path

        print(f"\n" + "="*80)
        print(f"✅ {len(image_paths)}/{len(prompts)}개 이미지 생성 완료")
        print("="*80)

        return image_paths

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        prompts = state.get("image_prompts", [])
        image_paths = self.generate_images_from_prompts(prompts)
        return {
            **state,
            "image_paths": image_paths
        }


# 헬퍼 함수들 (원본 그대로)

def load_prompts(prompts_path: str) -> List[Dict[str, Any]]:
    with open(prompts_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_image_manifest(
    image_paths: Dict[str, str],
    output_path: str
):
    manifest = {
        'total_images': len(image_paths),
        'images': [
            {
                'image_id': image_id,
                'path': path,
                'filename': os.path.basename(path)
            }
            for image_id, path in image_paths.items()
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n💾 이미지 매니페스트 저장: {output_path}")


def print_generation_summary(image_paths: Dict[str, str]):
    print("\n" + "="*80)
    print("📊 생성 결과 요약")
    print("="*80)

    print(f"\n총 {len(image_paths)}개 이미지:")

    for image_id, path in sorted(image_paths.items()):
        file_size = os.path.getsize(path) / 1024  # KB
        print(f"  - {image_id}: {os.path.basename(path)} ({file_size:.1f} KB)")


if __name__ == "__main__":
    print("Image Generation Node (copied from hyunsu)")

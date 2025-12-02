# app/services/langgraph_service.py
import os, asyncio
import httpx
from typing import List, Dict, Any

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")  # 예: http://localhost:3001/api

async def run_langgraph(
    prompt: str,
    input_paths: List[str],
    options: Dict[str, Any],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    payload = {
        "prompt": prompt,
        "inputs": input_paths,
        "options": options,
        "metadata": metadata,  # 여기서 input_document_ids 등 기록
    }

    # LangGraph endpoint가 아직 없으면 더미로 처리
    if not LANGGRAPH_URL:
        await asyncio.sleep(1)
        # 더미 결과 예시
        return {
            "run_id": "dummy-run-123",
            "outputs": {
                "script": "[00:00.000] 더미 스크립트입니다.\n",
                "slides": [
                    {
                        "slide_index": 0,
                        "image_bytes_b64": None,  # 테스트면 생략 가능
                        "image_ext": "png",
                        "start_time": 0.0,
                        "end_time": 5.0,
                        "slide_content": "슬라이드 1 설명"
                    }
                ],
                "audio": {
                    "audio_bytes_b64": None,
                    "audio_ext": "mp3"
                }
            }
        }

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{LANGGRAPH_URL}/run", json=payload, timeout=120.0)
        r.raise_for_status()
        return r.json()


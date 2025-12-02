# backend/app/routers/outputs.py
from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from datetime import datetime, timedelta
from uuid import uuid4
import json
import uuid, base64
from typing import Any, Dict, List

from app.services.supabase_service import supabase, upload_bytes
from app.services.langgraph_service import run_langgraph  # optional

router = APIRouter(prefix="/outputs", tags=["outputs"])

# 프로젝트 output 목록 조회
@router.get("/list")
def get_outputs(project_id: int):
    try:
        res = supabase.table("output_contents") \
            .select("id, title, created_at, storage_path") \
            .eq("project_id", project_id) \
            .order("created_at", desc=True) \
            .execute()

        return {"outputs": res.data or []}

    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="출력 목록 불러오기 실패")

# output 상세 조회
@router.get("/{output_id}")
def get_output_detail(output_id: int):
    # output_contents 가져오기
    content_res = supabase.table("output_contents") \
        .select("*") \
        .eq("id", output_id) \
        .single() \
        .execute()

    if content_res.data is None:
        raise HTTPException(status_code=404, detail="Output not found")

    # output_images 가져오기
    images_res = supabase.table("output_images") \
        .select("*") \
        .eq("output_id", output_id) \
        .order("img_index", desc=False) \
        .execute()

    return {
        "output": content_res.data,
        "images": images_res.data
    }

# output 생성 - LangGraph 호출
@router.post("/generate")
async def generate_output(
    project_id: int,
    user_id: str = Form(...),
    title: str = Form("새 에피소드"),
    input_content_ids: str = Form("[]"),
    host1: str = Form(""),
    host2: str = Form(""),
    style: str = Form("default")
):
    try:
        input_ids = json.loads(input_content_ids)

        # LangGraph 호출 (스크립트 + 오디오 + 이미지 + 요약문 생성)
        result = await run_langgraph(
            input_ids=input_ids,
            host1=host1,
            host2=host2,
            style=style,
        )

        script_text = result["script"]
        audio_url = result["audio_url"]
        images = result.get("images", [])  # [{image_path, img_description, img_index} ...]


        # output_contents 저장
        out_res = supabase.table("output_contents").insert({
            "project_id": project_id,
            "user_id": user_id,
            "title": title,
            "input_content_ids": input_ids,
            "script_text": script_text,
            "storage_path": audio_url,
            "options": {
                "host1": host1,
                "host2": host2,
                "style": style
            },
            "metadata": {
                "image_count": len(images)
            }
        }).execute()

        output_id = out_res.data[0]["id"]

        # 이미지가 있다면 output_images 에 저장
        if len(images) > 0:
            for img in images:
                supabase.table("output_images").insert({
                    "output_id": output_id,
                    "image_path": img["path"],
                    "img_description": img.get("img_description", ""),
                    "img_index": img.get("img_index", 0),
                }).execute()

        return {"output": out_res.data[0]}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="팟캐스트 생성 실패")
    
# backend/app/routers/output.py
from fastapi import APIRouter, Form, BackgroundTasks, HTTPException
import json
import requests
from app.services.supabase_service import supabase, SUPABASE_URL, SUPABASE_SERVICE_KEY, normalize_supabase_response
from app.services.langgraph_service import run_langgraph  # optional

router = APIRouter(prefix="/outputs", tags=["outputs"])

# 프로젝트 output 목록 조회
@router.get("/list")
def get_outputs(project_id: int):
    try:
        res = supabase.table("output_contents") \
            .select("id, title, created_at, audio_path, script_path") \
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

# output 상태 조회 - 프론트에서 polling 용도
@router.get("/{output_id}/status")
def get_output_status(output_id: int):
    res = supabase.table("output_contents") \
        .select("status") \
        .eq("id", output_id) \
        .single() \
        .execute()

    if res.data is None:
        raise HTTPException(status_code=404, detail="Output not found")

    return res.data

# output 삭제
@router.delete("/{output_id}")
def delete_output(output_id: int):
    try:
        # 존재 여부 확인
        raw = (
            supabase.table("output_contents")
            .select("id, storage_path")
            .eq("id", output_id)
            .execute()
        )

        normalized = normalize_supabase_response(raw)
        rows = normalized["data"]

         # row 없으면 이미 삭제된 상태 -> 성공 처리
        if not rows:
            return {"message": "이미 삭제된 상태입니다.", "deleted_id": output_id}

        check = rows[0]

        # DB 삭제
        url = f"{SUPABASE_URL}/rest/v1/output_contents?id=eq.{output_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Prefer": "return=minimal",
        }

        res_del = requests.delete(url, headers=headers)

        if res_del.status_code not in (200, 204):
            print("Delete error:", res_del.text)
            raise HTTPException(status_code=500, detail="DB 삭제 실패")

        # Storage 삭제
        storage_path = check.get("storage_path")
        if storage_path:
            supabase.storage.from_("outputs").remove([storage_path])

        return {"message": "삭제 완료", "deleted_id": output_id}

    except HTTPException:
        raise
    except Exception as e:
        print("output 삭제 오류:", e)
        raise HTTPException(status_code=500, detail="output 소스 삭제 실패")

# generate: output 생성 요청 -> output_contents row 생성 + 비동기 LangGraph 실행
@router.post("/generate")
async def generate_output(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    title: str = Form("새 팟캐스트"),
    input_content_ids: str = Form("[]"),
    host1: str = Form(""),
    host2: str = Form(""),
    style: str = Form("default"),
):
    try:
        # title이 빈 문자열("")일 때 기본값 설정
        title = (title or "새 팟캐스트").strip()

        input_ids = json.loads(input_content_ids)

        # output_contents row 생성
        out_res = supabase.table("output_contents").insert({
            "project_id": project_id,
            "title": title,
            "input_content_ids": input_ids,
            "options": {
                "host1": host1,
                "host2": host2,
                "style": style
            },
            "status": "processing", # default status : processing(생성 중)
        }).execute()

        output_id = out_res.data[0]["id"]

        # Background로 LangGraph 실행
        background_tasks.add_task(
            process_langgraph_output,
            output_id=output_id,
            input_ids=input_ids,
            host1=host1,
            host2=host2,
            style=style,
        )

        return {
            "output_id": output_id,
            "status": "processing"
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="출력 생성 요청 실패")

# 백그라운드에서 LangGraph 실행 -> output_contents, output_images 업데이트
async def process_langgraph_output(output_id, input_ids, host1, host2, style):
    try:

        # input_ids기반으로  실제 Storage URL 또는 link_url 조회
        rows = (
            supabase.table("input_contents")
            .select("id, is_link, storage_path, link_url")
            .in_("id", input_ids)
            .execute()
        )

        if not rows.data:
            raise Exception("input_contents 조회 실패")

        source_urls = []
        for item in rows.data:
            if item["is_link"]:
                source_urls.append(item["link_url"])
            else:
                source_urls.append(item["storage_path"])

        # 테스트 출력
        print("==== LangGraph 호출 예정 데이터 ====")
        print("output_id:", output_id)
        print("source_urls:", source_urls)
        print("host1:", host1)
        print("host2:", host2)
        print("style:", style)

        # LangGraph 실행
        # result = await run_langgraph(
        #     output_id=output_id,
        #     source_urls=source_urls,
        #     host1=host1,
        #     host2=host2,
        #     style=style
        # )

        # 성공 시 output_contents 업데이트 (임시)
    #    supabase.table("output_contents").update({
    #         "status": "completed",
    #         "script_text": result.get("script"),         # 스크립트 내용 자체
    #         "summary": result.get("summary"),
    #         "title": result.get("title"),
    #         "audio_path": result.get("audio_url"),       # 오디오 파일 경로 저장
    #         "script_path": result.get("script_url"),     # 스크립트 txt 파일 경로 저장
    #         "metadata": {
    #             "image_count": len(result.get("images", []))
    #         }
    #     }).eq("id", output_id).execute()

        # 이미지 여러개 처리하는 걸로 바꿔야 함
    #    supabase.table("output_images").insert({
    #         "image_path": result.get("image_path"),       # 이미지 파일 경로 저장
    #         "img_index": result.get("img_index"),
    #         "img_description": result.get("img_description"),
    #         "start_time": result.get("start_time"),
    #         "end_time": result.get("end_time")
    #     }).eq("id", output_id).execute()

        # 임시 -> 바로 성공(완료) 처리
        supabase.table("output_contents").update({
            "status": "completed",
        }).eq("id", output_id).execute()
        
    except Exception as e:
        print("[LangGraph Error]", e)
        supabase.table("output_contents").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", output_id).execute()
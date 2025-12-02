from fastapi import APIRouter, HTTPException
from app.services.supabase_service import supabase, delete_project_folder
from datetime import datetime

router = APIRouter()

# 프로젝트 목록 조회
@router.get("/projects")
def list_projects(user_id: str):
    res = supabase.table("projects") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    return res.data

# 새 프로젝트 생성
@router.post("/projects/create")
def create_project(payload: dict):
    user_id = payload["user_id"]

    # 유저의 기존 프로젝트 개수 조회
    count_res = supabase.table("projects") \
        .select("id") \
        .eq("user_id", user_id) \
        .execute()

    project_count = len(count_res.data)

    # 자동 이름 생성 - 지금 이거 안 됨
    title = payload.get("title", f"프로젝트 {project_count + 1}")
    description = payload.get("description", "")

    res = supabase.table("projects").insert({
        "user_id": user_id,
        "title": title,
        "description": description,
    }).execute()

    return {"project": res.data[0]}


# 프로젝트 폴더 및 파일 삭제
@router.delete("/projects/{project_id}")
def delete_project(project_id: int, user_id: str):
    """
    1. project 삭제
    2. input_contents / output_contents 삭제
    3. Supabase Storage 파일 삭제
    """

    # 0) 프로젝트 존재 확인
    proj = supabase.table("projects") \
        .select("*") \
        .eq("id", project_id) \
        .eq("user_id", user_id) \
        .execute()

    if not proj.data:
        raise HTTPException(404, "Project not found")

    # 1) input_contents, output_contents 삭제
    supabase.table("input_contents").delete().eq("project_id", project_id).execute()
    supabase.table("output_contents").delete().eq("project_id", project_id).execute()

    # 2) projects 테이블에서 삭제
    supabase.table("projects").delete().eq("id", project_id).execute()

    # 3) Supabase Storage 파일 삭제
    delete_project_folder(user_id, project_id)

    return {"message": "project deleted", "project_id": project_id}





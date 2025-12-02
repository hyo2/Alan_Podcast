from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()   # .env 파일 읽기

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# CORS 설정 (React와 통신)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate/")
async def generate(
    text: str = Form(...),
    files: list[UploadFile] = File(None)
):
    uploaded_urls = []

    # Supabase Storage 업로드
    if files:
        for file in files:
            content = await file.read()
            path = f"uploads/{file.filename}"
            supabase.storage.from_("source_bucket").upload(path, content)
            url = supabase.storage.from_("source_bucket").get_public_url(path)
            uploaded_urls.append(url)

    # LangGraph 호출 (더미)
    # 실제 호출 시, HTTP request 또는 SDK 사용
    async def dummy_langgraph(text, urls):
        await asyncio.sleep(1)  # simulate processing
        return {"script": f"Generated script for '{text}'", "files": urls}

    result = await dummy_langgraph(text, uploaded_urls)
    return result

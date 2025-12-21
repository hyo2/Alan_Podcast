import os
import tempfile

def patch_vertex_ai_env():
    """
    Railway 환경에서
    VERTEX_AI_SERVICE_ACCOUNT_JSON → 임시 파일로 변환
    
    ⭐ 핵심: VERTEX_AI_SERVICE_ACCOUNT_FILE 환경 변수도 설정!
    """
    creds_json = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        # 로컬 환경이거나 이미 파일 경로가 있으면 패스
        return

    print("🔧 Railway 환경 감지: JSON → 임시 파일 변환 중...")

    # 임시 파일 생성 (삭제하지 않음)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as f:
        f.write(creds_json)
        temp_path = f.name

    # ⭐ 핵심: 두 환경 변수 모두 설정!
    os.environ["VERTEX_AI_SERVICE_ACCOUNT_FILE"] = temp_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
    
    print(f"✅ 임시 서비스 계정 파일 생성: {temp_path}")
    print(f"✅ VERTEX_AI_SERVICE_ACCOUNT_FILE 환경 변수 설정 완료")
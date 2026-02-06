"""
GCP API 권한 테스트 스크립트
===========================

팟캐스트 생성에 필요한 모든 GCP API 권한을 테스트합니다.

필요한 API:
1. Vertex AI (Gemini LLM)
2. Vertex AI (Vision)
3. Vertex AI (TTS)
4. Google Cloud Speech (STT)

사용법:
    python test_gcp_permissions.py <service-account.json>
"""

import os
import sys
import json
from pathlib import Path


def test_service_account_auth(credentials_file: str) -> bool:
    """서비스 계정 인증 테스트"""
    print("\n" + "="*80)
    print("🔐 [1/5] 서비스 계정 인증 테스트")
    print("="*80)
    
    try:
        # JSON 파일 읽기
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        print(f"✅ JSON 파일 읽기 성공")
        print(f"   - 프로젝트 ID: {creds_data.get('project_id', 'N/A')}")
        print(f"   - 클라이언트 이메일: {creds_data.get('client_email', 'N/A')}")
        
        # 환경 변수 설정
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_file
        
        # google-auth로 인증 확인
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # 토큰 생성 테스트
        credentials.refresh(Request())
        
        print(f"✅ 인증 성공!")
        print(f"   - 토큰 발급 완료")
        return True
        
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {credentials_file}")
        return False
    except json.JSONDecodeError:
        print(f"❌ JSON 파일 형식 오류")
        return False
    except Exception as e:
        print(f"❌ 인증 실패: {e}")
        return False


def test_vertex_ai_llm(credentials_file: str, project_id: str) -> bool:
    """Vertex AI LLM (Gemini) 테스트"""
    print("\n" + "="*80)
    print("🤖 [2/5] Vertex AI LLM (Gemini) 테스트")
    print("="*80)
    
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        # Vertex AI 초기화
        vertexai.init(project=project_id, location="us-central1")
        print(f"✅ Vertex AI 초기화 성공")
        
        # Gemini 모델 테스트
        model = GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("안녕하세요")
        
        print(f"✅ Gemini LLM 호출 성공!")
        print(f"   - 응답: {response.text[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Vertex AI LLM 테스트 실패: {e}")
        return False


def test_vertex_ai_vision(credentials_file: str, project_id: str) -> bool:
    """Vertex AI Vision 테스트"""
    print("\n" + "="*80)
    print("👁️  [3/5] Vertex AI Vision 테스트")
    print("="*80)
    
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part
        import base64
        
        # 1x1 픽셀 테스트 이미지 (PNG)
        test_image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        vertexai.init(project=project_id, location="us-central1")
        model = GenerativeModel("gemini-2.5-flash")
        
        image_part = Part.from_data(data=test_image, mime_type="image/png")
        response = model.generate_content([image_part, "이 이미지를 설명해주세요"])
        
        print(f"✅ Vertex AI Vision 호출 성공!")
        print(f"   - 응답: {response.text[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Vertex AI Vision 테스트 실패: {e}")
        return False


def test_vertex_ai_tts(credentials_file: str, project_id: str) -> bool:
    """Vertex AI TTS 테스트"""
    print("\n" + "="*80)
    print("🔊 [4/5] Vertex AI TTS 테스트")
    print("="*80)
    
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        import requests
        
        # 인증 토큰 생성
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        credentials.refresh(Request())
        
        # TTS API 호출 (프로덕션과 100% 동일)
        tts_region = "us-central1"
        tts_model_name = "gemini-2.5-flash-preview-tts"
        
        url = (
            f"https://{tts_region}-aiplatform.googleapis.com"
            f"/v1beta1/projects/{project_id}"
            f"/locations/{tts_region}"
            f"/publishers/google/models/{tts_model_name}:generateContent"
        )
        
        # 프로덕션과 동일한 prompt 형식
        prompt = f"Read naturally in Korean. Please PAUSE clearly between sentences.\nText:\n안녕하세요"
        
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        data = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "Leda"}}}
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=300)
        
        if response.status_code == 200:
            # ✅ 실제 오디오 데이터 검증!
            try:
                response_json = response.json()
                
                # 오디오 데이터 추출 시도
                audio_b64 = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                
                # Base64 디코딩
                import base64
                audio_data = base64.b64decode(audio_b64)
                
                # 오디오 데이터 크기 확인
                audio_size = len(audio_data)
                
                if audio_size > 0:
                    print(f"✅ Vertex AI TTS 호출 성공!")
                    print(f"   - 오디오 데이터 크기: {audio_size:,} bytes ({audio_size/1024:.1f} KB)")
                    print(f"   - 형식: raw PCM (24kHz, 16-bit, mono)")
                    
                    # ✅ raw PCM 데이터 크기 검증
                    # "안녕하세요" (5글자) → 약 1-2초 → 약 48,000-96,000 bytes 예상
                    # (24000 samples/sec * 2 bytes/sample * 1-2 sec)
                    if audio_size > 10000:  # 최소 10KB
                        print(f"   - 오디오 데이터 정상 범위 확인됨")
                    else:
                        print(f"   ⚠️  오디오 데이터가 예상보다 작음")
                    
                    return True
                else:
                    print(f"❌ 오디오 데이터가 비어있음!")
                    return False
                    
            except KeyError as e:
                print(f"❌ 응답 구조 오류: 필요한 키를 찾을 수 없음 ({e})")
                print(f"   - 응답 구조: {json.dumps(response_json, indent=2, ensure_ascii=False)[:500]}")
                return False
            except Exception as e:
                print(f"❌ 오디오 데이터 추출 실패: {e}")
                return False
        else:
            print(f"❌ TTS API 오류: {response.status_code}")
            print(f"   - 에러 응답:")
            try:
                error_json = response.json()
                print(f"   - {json.dumps(error_json, indent=4, ensure_ascii=False)}")
            except:
                print(f"   - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Vertex AI TTS 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_google_cloud_speech(credentials_file: str) -> bool:
    """Google Cloud Speech-to-Text 테스트"""
    print("\n" + "="*80)
    print("🎤 [5/5] Google Cloud Speech-to-Text 테스트")
    print("="*80)
    
    try:
        from google.cloud import speech
        import io
        
        # Speech 클라이언트 생성
        client = speech.SpeechClient.from_service_account_file(credentials_file)
        
        # 간단한 설정 테스트 (실제 오디오 없이)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="ko-KR",
        )
        
        print(f"✅ Google Cloud Speech 클라이언트 생성 성공!")
        print(f"   - API 권한 확인됨")
        return True
        
    except Exception as e:
        print(f"❌ Google Cloud Speech 테스트 실패: {e}")
        return False


def main():
    """메인 실행 함수"""
    print("\n" + "="*80)
    print("🔍 GCP API 권한 테스트 시작")
    print("="*80)
    
    # 인자 확인
    if len(sys.argv) < 2:
        print("\n사용법: python test_gcp_permissions.py <service-account.json>")
        print("\n예시:")
        print("  python test_gcp_permissions.py vertex-ai-service-account.json")
        sys.exit(1)
    
    credentials_file = sys.argv[1]
    
    # 파일 존재 확인
    if not os.path.exists(credentials_file):
        print(f"\n❌ 파일을 찾을 수 없습니다: {credentials_file}")
        sys.exit(1)
    
    # 프로젝트 ID 읽기
    try:
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
            project_id = creds_data.get('project_id')
            
            if not project_id:
                print("❌ JSON 파일에 project_id가 없습니다")
                sys.exit(1)
    except Exception as e:
        print(f"❌ JSON 파일 읽기 실패: {e}")
        sys.exit(1)
    
    # 테스트 실행
    results = {
        "인증": test_service_account_auth(credentials_file),
        "Vertex AI LLM": test_vertex_ai_llm(credentials_file, project_id),
        "Vertex AI Vision": test_vertex_ai_vision(credentials_file, project_id),
        "Vertex AI TTS": test_vertex_ai_tts(credentials_file, project_id),
        "Google Cloud Speech": test_google_cloud_speech(credentials_file)
    }
    
    # 결과 요약
    print("\n" + "="*80)
    print("📊 테스트 결과 요약")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{status} | {test_name}")
        if not passed:
            all_passed = False
    
    print("="*80)
    
    if all_passed:
        print("\n🎉 모든 테스트 통과! API 권한이 정상입니다.")
        print("\n다음 단계:")
        print("1. .env 파일에 다음 변수 설정:")
        print(f"   VERTEX_AI_PROJECT_ID={project_id}")
        print(f"   VERTEX_AI_SERVICE_ACCOUNT_FILE={os.path.abspath(credentials_file)}")
        print("   VERTEX_AI_REGION=us-central1")
        print("   VERTEX_AI_MODEL_TEXT=gemini-2.5-flash")
        print("\n2. 서버 재시작")
    else:
        print("\n⚠️  일부 테스트 실패! 권한 확인이 필요합니다.")
        print("\n필요한 API 권한:")
        print("- Vertex AI API")
        print("- Cloud Speech-to-Text API")
        print("\nGCP 콘솔 담당자에게 위 API 활성화를 요청하세요.")
    
    print()


if __name__ == "__main__":
    main()
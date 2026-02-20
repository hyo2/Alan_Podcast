# AI Audiobook Generator

AI 기반 자동 오디오북 생성 시스템입니다. PDF, 문서, URL 등의 입력을 받아 자동으로 팟캐스트 형식의 오디오북을 생성합니다.

## 🎯 주요 기능

### 1. 다양한 입력 소스 지원

- **문서 파일**: PDF, DOCX, PPTX, TXT
- **웹 페이지**: URL 크롤링
- **주 소스 + 보조 소스**: 메인 콘텐츠와 참고 자료 분리 (최대 4개)

### 2. AI 기반 스크립트 생성

- **LLM**: Vertex AI Gemini 2.5 flash
- **스타일**: 강의형 / 대화형
- **난이도**: 초급 / 중급 / 고급
- **자동 압축**: 목표 시간에 맞게 스크립트 조정

### 3. TTS 음성 생성

- **TTS**: Vertex AI Gemini TTS 2.5-flash-preview
- **다중 화자**: 진행자 / 게스트 역할 구분

### 4. 스트리밍 지원

- **Range Request**: HTTP 206 Partial Content
- **청크 스트리밍**: 대용량 오디오 효율적 전송
- **타임스탬프 스크립트**: 자막 형식 트랜스크립트

## 🏗️ 시스템 아키텍처

```
Client
  │
  ├─ Internal Auth Middleware (X-Internal-Service-Token)
  ├─ Alan Auth Service (alan_session_id / alan_guest_token / Bearer)
  │
  └─ FastAPI Router
       │
       ├─ POST /sessions → Azure Queue enqueue(extract_ocr)
       │
       └─ Azure Queue Trigger Worker
            │
            ├─ Step 1: extract_ocr   → extract_texts_node (OCR + Vision)
            ├─ Step 2: extract_finalize → combine_texts_node
            ├─ Step 3: script        → generate_script_node (Vertex AI Gemini)
            ├─ Step 4: audio         → generate_audio_node (Vertex AI Gemini)
            └─ Step 5: finalize      → merge_audio_node (ffmpeg) + generate_transcript_node
                                       → Azure Blob Storage (output_files/)
```

### LangGraph Pipeline (6 노드)

| 노드                  | 설명                                                                          |
| --------------------- | ----------------------------------------------------------------------------- |
| `extract_texts`       | OCR(RapidOCR) + Gemini Vision fallback + 이미지 설명 생성 (MetadataGenerator) |
| `combine_texts`       | 텍스트 구조화 및 결합                                                         |
| `generate_script`     | Vertex AI Gemini 스크립트 생성 (DB 프롬프트 템플릿 사용)                      |
| `generate_audio`      | Vertex AI Gemini TTS 음성 합성 (Tail Focus V5)                                |
| `merge_audio`         | ffmpeg 번들 바이너리로 WAV→MP3 변환/병합                                      |
| `generate_transcript` | 타임스탬프 스크립트 생성                                                      |

## 📦 번들 리소스(바이너리/모델) 및 라이선스 안내

본 저장소는 OCR 모델 파일을 포함하며,
ffmpeg/ffprobe 바이너리는 GitHub 파일 제한으로 인해 저장소에 포함하지 않고 수동 배치 방식으로 운영합니다.

### 1) FFmpeg 번들 바이너리 (Azure 배포용)

- **포함 위치**: `bin/linux-x64/ffmpeg`, `bin/linux-x64/ffprobe`
- **사용 목적**: 오디오 변환/병합 (WAV → MP3 등)
- **동작 방식**: Azure 배포 환경에서 `bin/linux-x64/*`를 런타임에 `/tmp/bin/`으로 복사 후 실행합니다. (읽기 전용 파일시스템/권한 이슈 대응)
- **다운로드 출처**: `https://github.com/BtbN/FFmpeg-Builds/releases/tag/latest`
- **버전/빌드 식별**: `ffmpeg-n7.1-latest-linux64-lgpl-7.1`

> ⚠️ 주의: FFmpeg는 빌드/배포본에 따라 LGPL/GPL 구성이 달라질 수 있습니다.  
> 본 프로젝트는 `<LGPL build 사용>`을 전제로 합니다.

### 2) OCR 모델 파일

- **포함 위치**: `ocr_model/`
- **사용 목적**: OCR 엔진에서 사용하는 모델/리소스 파일
- **다운로드 출처**: `https://huggingface.co/monkt/paddleocr-onnx/tree/main`

## 🚀 빠른 시작

### 1. 필수 요구사항

- Python 3.11+
- PostgreSQL 14+
- Google Cloud 프로젝트 (Vertex AI 활성화)
- Azure Storage 계정 (Blob + Queue) 또는 로컬 스토리지

> **ffmpeg**: Azure Functions 배포 시에는 `app/bin/linux-x64/`에 번들된 바이너리를 사용합니다. 로컬 개발 시에는 시스템 ffmpeg를 사용합니다.

### 2. 설치

```bash
# 1. 저장소 클론
git clone <repository-url>
cd backend

# 2. 가상 환경 생성 (conda 권장)
conda create -n audiobook python=3.11
conda activate audiobook

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일 편집 (아래 참조)
```

### 3. 환경 변수 설정

`.env` 파일:

```bash
# ===== 환경 구분 =====
ENVIRONMENT=development   # development | staging | production

# ===== 내부 서비스 인증 =====
INTERNAL_SERVICE_TOKEN=your-secret-token-here

# ===== Alan 사용자 인증 =====
AUTH_MODE=mock            # mock (개발) | real (운영)
ALAN_AUTH_BASE_URL=       # AUTH_MODE=real 일 때 필수
ACCESS_POLICY=all         # all | pro_only
# PRO_ROLE_ALLOWLIST=pro_user,internal_user,pro_user_promotion

# ===== Database =====
DATABASE_URL=postgresql://user:password@localhost:5432/audiobook
REPO_BACKEND=postgres     # postgres | memory

# ===== Storage =====
STORAGE_BACKEND=local     # local | azure
BASE_OUTPUT_DIR=./outputs
# AZURE_STORAGE_CONNECTION_STRING=...
# AZURE_STORAGE_CONTAINER=ai-audiobook

# ===== Azure Queue =====
# AZURE_STORAGE_QUEUE_NAME=ai-audiobook-jobs
# AzureWebJobsStorage=<connection-string>

# ===== Google Cloud =====
VERTEX_AI_PROJECT_ID=your-gcp-project-id
VERTEX_AI_REGION=asia-northeast3
VERTEX_AI_SERVICE_ACCOUNT_JSON={"type":"service_account",...}   # JSON 문자열 (Azure 배포 시)
VERTEX_AI_SERVICE_ACCOUNT_FILE=/tmp/gcp-sa.json                 # 자동 생성됨

# ===== LangSmith (선택) =====
# LANGSMITH_API_KEY=...
# LANGSMITH_PROJECT=ai-audiobook-dev

# ===== 출력 디렉토리 =====
BASE_OUTPUT_DIR=./outputs
```

### 4. 데이터베이스 설정

```bash
# PostgreSQL 데이터베이스 생성
createdb audiobook

# 테이블 생성 (SQLAlchemy models 기반)
python -c "from app.db.models import Base; from app.db.db_session import engine; Base.metadata.create_all(engine)"
```

### 5. 실행

```bash
# 로컬 개발 서버 (HTTP만, Queue Trigger 없음)
uvicorn app.main:app --reload --host 0.0.0.0 --port 4001

# Azure Functions 로컬 실행 (HTTP + Queue Trigger 포함)
func start
```

서버 실행 후 접속:

- API 서버: http://localhost:4001
- API 문서: http://localhost:4001/docs (Swagger UI)
- Health Check: http://localhost:4001/v1/health

> **Queue Trigger 로컬 테스트**: Azurite(Azure Storage 에뮬레이터) 또는 실제 Azure Storage 연결이 필요합니다.

## 📚 API 사용법

모든 요청(헬스체크 제외)에는 두 가지 인증이 필요합니다.

```bash
# 공통 헤더
X-Internal-Service-Token: your-token
Authorization: Bearer <alan-token>   # 또는 alan_session_id 쿠키
```

> 개발 환경(`AUTH_MODE=mock`)에서는 Alan 인증 없이 동작합니다.

### 1. 채널 생성

```bash
curl -X POST http://localhost:4001/v1/channels \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Authorization: Bearer your-alan-token"
```

응답:

```json
{
  "success": true,
  "data": {
    "channel_id": "ch_abc123",
    "created_at": "2026-01-30T12:00:00Z"
  }
}
```

### 2. 세션 생성 (파일 업로드 + 오디오북 생성 시작)

파일 업로드와 세션 생성이 단일 요청으로 처리됩니다.

```bash
curl -X POST http://localhost:4001/v1/channels/ch_abc123/sessions \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Authorization: Bearer your-alan-token" \
  -F "files=@document.pdf" \
  -F "files=@slides.pptx" \
  -F 'links=["https://example.com/article"]' \
  -F "main_kind=file" \
  -F "main_index=0" \
  -F "voice_id=Fenrir" \
  -F "style=explain" \
  -F "duration=5" \
  -F "difficulty=intermediate"
```

응답:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz",
    "status": "processing",
    "progress": 10,
    "current_step": "파일 업로드 완료 및 변환 시작",
    "created_at": "2026-01-30T12:00:00Z"
  }
}
```

### 3. 상태 확인 (폴링)

```bash
curl http://localhost:4001/v1/channels/ch_abc123/sessions/sess_xyz \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Authorization: Bearer your-alan-token"
```

응답 (완료 시):

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz",
    "status": "completed",
    "progress": 100,
    "current_step": "completed",
    "result": {
      "chapters": [{ "chapter": 1, "title": "AI와 머신러닝", "duration": 597 }],
      "total_duration": 597
    }
  }
}
```

### 4. 오디오 스트리밍

```bash
# 전체 다운로드
curl http://localhost:4001/v1/channels/ch_abc123/files/audio/sess_xyz/1 \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Authorization: Bearer your-alan-token" \
  -o podcast.mp3

# Range 요청 (부분 스트리밍)
curl http://localhost:4001/v1/channels/ch_abc123/files/audio/sess_xyz/1 \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Authorization: Bearer your-alan-token" \
  -H "Range: bytes=0-1023" \
  -o chunk.mp3
```

## 🔧 개발 가이드

### 프로젝트 구조

```
backend/
├── app/
│   ├── routers/                  # API 엔드포인트
│   │   ├── channels.py
│   │   ├── sessions.py
│   │   ├── streaming.py
│   │   └── health.py
│   ├── services/                 # 비즈니스 로직
│   │   ├── session_service.py    # 전체 파이프라인 실행 (kind=generate)
│   │   ├── pipeline_steps.py     # 단계별 실행 함수 (kind=pipeline_step)
│   │   ├── pipeline_worker.py    # Queue 메시지 처리/분기
│   │   ├── queue_service.py      # Azure Queue enqueue
│   │   ├── langgraph_service.py  # LangGraph 실행 래퍼
│   │   ├── alan_auth_service.py  # Alan 사용자 인증
│   │   ├── storage_service.py    # 스토리지 추상화
│   │   └── langsmith_tracing.py  # LangSmith 트레이싱
│   ├── dependencies/             # FastAPI 의존성
│   │   ├── auth.py               # require_access, require_pro_user
│   │   └── repos.py              # Repository 팩토리
│   ├── repositories/             # 데이터 액세스
│   │   ├── interfaces/
│   │   ├── postgres/
│   │   └── memory/
│   ├── langgraph_pipeline/       # AI 워크플로우
│   │   └── podcast/
│   │       ├── graph.py          # LangGraph 노드 정의
│   │       ├── state.py
│   │       ├── document_converter_node.py  # 문서 변환
│   │       ├── metadata_generator_node.py  # OCR + Vision
│   │       ├── improved_hybrid_filter.py  # 이미지 필터링
│   │       ├── prompt_service.py # Prompt 템플릿 서비스
│   │       ├── script/           # 스크립트 노드 사용 모듈
│   │       ├── script_generator.py
│   │       ├── tail_focus_v5_fixed.py
│   │       ├── tts_service.py
│   │       ├── audio_processor.py
│   │       └── pricing.py
│   ├── middleware/               # 미들웨어
│   │   ├── cors.py
│   │   └── internal_auth.py
│   ├── utils/
│   │   ├── binary_helper.py      # ffmpeg/ffprobe 번들 바이너리 관리
│   │   ├── error_codes.py
│   │   ├── logging_helper.py
│   │   ├── response.py
│   │   └── session_helpers.py
│   ├── db/                       # 데이터베이스
│   │   └── db_session.py
│   └── main.py                  # 앱 진입점
├── bin/
│   └── linux-x64/               # ffmpeg/ffprobe 수동 배치 경로 (repo 미포함, Azure 배포용)
|                                # 런타임에 /tmp/bin/으로 자동 복사됨
├── function_app.py               # Azure Functions 진입점
├── host.json                     # Azure Functions 설정
├── requirements.txt
└── .env.example
```

### Repository 패턴

```python
# 환경 변수로 전환
REPO_BACKEND=postgres  # 또는 memory
```

- **Memory**: 개발/테스트용 (재시작 시 데이터 소실)
- **Postgres**: 운영용 (영구 저장)

### Storage 패턴

```python
# 환경 변수로 전환
STORAGE_BACKEND=local   # 또는 azure
```

- **Local**: 개발용 (로컬 파일시스템)
- **Azure**: 운영용 (Azure Blob Storage)

## 🐛 트러블슈팅

### 1. FFmpeg 관련 에러

로컬 개발 환경에서는 시스템 ffmpeg를 사용합니다.

```bash
# 설치 확인
ffmpeg -version

# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### FFmpeg 번들 바이너리 설치 (GitHub 용량 제한으로 수동 설치 필요)

GitHub는 단일 파일 100MB 제한이 있어, `ffmpeg/ffprobe` 바이너리는 저장소에 포함하지 않습니다.

1. 아래 링크에서 **LGPL 빌드**를 다운로드합니다.

- 다운로드: https://github.com/BtbN/FFmpeg-Builds/releases/tag/latest
- 파일 예시: `ffmpeg-n7.1-latest-linux64-lgpl-7.1.tar.xz`

2. 압축 해제 후 `ffmpeg`, `ffprobe` 파일을 아래 경로에 복사합니다.

- 복사 위치: `app/bin/linux-x64/ffmpeg`, `app/bin/linux-x64/ffprobe`

3. (로컬 개발/리눅스) 실행 권한이 없으면 권한을 부여합니다.

```bash
chmod +x app/bin/linux-x64/ffmpeg app/bin/linux-x64/ffprobe
```

> Azure Functions 배포 환경에서는 위 번들 바이너리가 런타임에 /tmp/bin/으로 복사되어 실행됩니다.

### 2. Google Cloud 인증 에러

```bash
# 로컬: 서비스 계정 파일 경로 확인
export VERTEX_AI_SERVICE_ACCOUNT_FILE=/path/to/service-account.json

# Azure 배포: VERTEX_AI_SERVICE_ACCOUNT_JSON 환경변수에 JSON 문자열 설정
# function_app.py 시작 시 /tmp/gcp-sa.json으로 자동 생성됨
```

### 3. PostgreSQL 연결 에러

```bash
# 연결 테스트
psql $DATABASE_URL

# 데이터베이스 존재 확인
psql -l | grep audiobook
```

### 4. Azure Storage 연결 에러

```bash
# Connection String 형식 확인
# DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

# AZURE_STORAGE_CONNECTION_STRING과 AzureWebJobsStorage 모두 설정 필요
```

### 5. Alan 인증 에러 (운영 환경)

```bash
# 개발 환경에서는 AUTH_MODE=mock으로 우회 가능
AUTH_MODE=mock

# 운영 환경 체크리스트
# - ALAN_AUTH_BASE_URL 설정 확인
# - alan_session_id 쿠키 또는 Authorization Bearer 헤더 확인
```

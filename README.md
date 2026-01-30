# AI Audiobook Generator

AI 기반 자동 오디오북 생성 시스템입니다. PDF, 문서, URL 등의 입력을 받아 자동으로 팟캐스트 형식의 오디오북을 생성합니다.

## 🎯 주요 기능

### 1. 다양한 입력 소스 지원

- **PDF 문서**: 텍스트 추출 + 이미지 설명 생성
- **텍스트 파일**: 직접 텍스트 처리
- **URL**: 웹 페이지 크롤링
- **주 소스 + 보조 소스**: 메인 콘텐츠와 참고 자료 분리

### 2. AI 기반 스크립트 생성

- **LLM**: Vertex AI Gemini 1.5 Pro
- **스타일**: 강의형 / 대화형
- **난이도**: 초급 / 중급 / 고급
- **자동 압축**: 목표 시간에 맞게 스크립트 조정

### 3. 고품질 음성 합성

- **TTS**: Google Cloud Text-to-Speech
- **화자 구분**: 진행자 / 게스트
- **Tail Focus V5**: 실시간 발화 단위 병합
- **출력**: MP3 (192kbps)

### 4. 스트리밍 지원

- **Range Request**: HTTP 206 Partial Content
- **청크 스트리밍**: 대용량 오디오 효율적 전송
- **타임스탬프 스크립트**: 자막 형식 트랜스크립트

## 🏗️ 시스템 아키텍처

```
Client → FastAPI → SessionService → LangGraph Pipeline → Storage
                                   ↓
                              Vertex AI (Gemini)
                              Google Cloud TTS
                              FFmpeg
```

### LangGraph Pipeline (6단계)

1. **extract_texts**: 문서에서 텍스트/이미지 추출
2. **combine_texts**: 텍스트 구조화 및 결합
3. **generate_script**: AI 스크립트 생성
4. **generate_audio**: TTS 음성 합성
5. **merge_audio**: 오디오 병합 (FFmpeg)
6. **generate_transcript**: 타임스탬프 스크립트 생성

## 🚀 빠른 시작

### 1. 필수 요구사항

- Python 3.11+
- PostgreSQL 14+
- FFmpeg 4.x+
- Google Cloud 프로젝트 (Vertex AI, Cloud TTS 활성화)
- Azure Storage 계정 (또는 로컬 스토리지 사용)

### 2. 설치

```bash
# 1. 저장소 클론
git clone <repository-url>
cd backend

# 2. 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 시스템 의존성 설치 (Ubuntu/Debian)
sudo apt-get install ffmpeg postgresql-client

# 5. 환경 변수 설정
cp .env.example .env
# .env 파일 편집 (아래 참조)
```

### 3. 환경 변수 설정

`.env` 파일:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/audiobook
REPO_BACKEND=postgres

# Storage (개발 환경에서는 local 사용 가능)
STORAGE_BACKEND=local  # 또는 azure
BASE_OUTPUT_DIR=./outputs
# AZURE_STORAGE_CONNECTION_STRING=...
# AZURE_STORAGE_CONTAINER=audiobook-files

# Google Cloud
VERTEX_AI_PROJECT_ID=your-gcp-project-id
VERTEX_AI_REGION=asia-northeast3
VERTEX_AI_SERVICE_ACCOUNT_FILE=/path/to/service-account.json

# Security
INTERNAL_SERVICE_TOKEN=your-secret-token-here

# Environment
ENVIRONMENT=development
# CORS_ORIGINS=http://localhost:5173
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
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 production 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

서버 실행 후 접속:

- API 서버: http://localhost:8000
- API 문서: http://localhost:8000/docs (Swagger UI)
- Health Check: http://localhost:8000/v1/health

## 📚 API 사용법

### 1. 채널 생성

```bash
curl -X POST http://localhost:8000/v1/channels \
  -H "X-Internal-Service-Token: your-secret-token"
```

응답:

```json
{
  "success": true,
  "data": {
    "channel_id": "ch_abc123",
    "created_at": "2024-01-30T12:00:00Z"
  }
}
```

### 2. 파일 업로드

```bash
curl -X POST http://localhost:8000/v1/channels/ch_abc123/sessions/sess_xyz/inputs \
  -H "X-Internal-Service-Token: your-secret-token" \
  -F "file=@document.pdf" \
  -F "role=main"
```

### 3. 세션 생성 (오디오북 생성 시작)

```bash
curl -X POST http://localhost:8000/v1/channels/ch_abc123/sessions \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "options": {
      "host1": "김선생",
      "host2": "이학생",
      "style": "explain",
      "duration": 5,
      "difficulty": "intermediate"
    }
  }'
```

### 4. 상태 확인

```bash
curl http://localhost:8000/v1/channels/ch_abc123/sessions/sess_xyz \
  -H "X-Internal-Service-Token: your-secret-token"
```

응답:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz",
    "status": "processing",
    "current_step": "generate_script",
    "title": null,
    "audio_key": null
  }
}
```

### 5. 오디오 스트리밍

```bash
# 전체 다운로드
curl http://localhost:8000/v1/channels/ch_abc123/files/audio/sess_xyz/1 \
  -H "X-Internal-Service-Token: your-secret-token" \
  -o podcast.mp3

# Range 요청 (부분 스트리밍)
curl http://localhost:8000/v1/channels/ch_abc123/files/audio/sess_xyz/1 \
  -H "X-Internal-Service-Token: your-secret-token" \
  -H "Range: bytes=0-1023" \
  -o chunk.mp3
```

## 🔧 개발 가이드

### 프로젝트 구조

```
backend/
├── app/
│   ├── routers/              # API 엔드포인트
│   │   ├── channels.py
│   │   ├── sessions.py
│   │   ├── streaming.py
│   │   └── health.py
│   ├── services/             # 비즈니스 로직
│   │   ├── session_service.py
│   │   ├── langgraph_service.py
│   │   └── storage_service.py
│   ├── repositories/         # 데이터 액세스
│   │   ├── postgres/
│   │   └── memory/
│   ├── langgraph_pipeline/   # AI 워크플로우
│   │   └── podcast/
│   │       ├── graph.py
│   │       ├── state.py
│   │       ├── script_generator.py
│   │       ├── tts_service.py
│   │       └── audio_processor.py
│   ├── middleware/           # 미들웨어
│   │   ├── cors.py
│   │   └── internal_auth.py
│   ├── db/                   # 데이터베이스
│   │   ├── models.py
│   │   └── db_session.py
│   └── main.py              # 앱 진입점
├── outputs/                  # 임시 출력 파일
├── requirements.txt
└── .env.*
```

### Repository 패턴

시스템은 Memory와 Postgres 백엔드를 모두 지원합니다:

```python
# 환경 변수로 전환
REPO_BACKEND=postgres  # 또는 memory
```

- **Memory**: 개발/테스트용 (재시작 시 데이터 소실)
- **Postgres**: Production용 (영구 저장)

### Storage 패턴

```python
# 환경 변수로 전환
STORAGE_BACKEND=local   # 또는 azure
```

- **Local**: 개발용 (로컬 파일시스템)
- **Azure**: Production용 (Azure Blob Storage)

## 🧪 테스트

```bash
# 단위 테스트
pytest tests/

# 특정 테스트
pytest tests/test_session_service.py

# 커버리지
pytest --cov=app tests/
```

## 📊 모니터링

### 로그 확인

```bash
# 실시간 로그
tail -f logs/app.log

# 에러 로그만
grep ERROR logs/app.log
```

### 세션 상태

세션의 `current_step` 필드로 진행 상황 추적:

- `start` → `extract_complete` → `combine_complete` → `script_complete` → `audio_complete` → `merge_complete` → `complete`
- `error`: 에러 발생 시

## 🐛 트러블슈팅

### 1. FFmpeg 관련 에러

```bash
# FFmpeg 설치 확인
ffmpeg -version

# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### 2. Google Cloud 인증 에러

```bash
# 서비스 계정 파일 권한 확인
chmod 600 /path/to/service-account.json

# 환경 변수 설정 확인
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### 3. PostgreSQL 연결 에러

```bash
# 연결 테스트
psql $DATABASE_URL

# 데이터베이스 존재 확인
psql -l | grep audiobook
```

### 4. Azure Blob Storage 연결 에러

```bash
# Connection String 형식 확인
# DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
```

# AI Audiobook Generator (Alan Pods)

> AI 기반 자동 오디오북 생성 시스템  
> 문서를 업로드하면 자동으로 팟캐스트 형식의 오디오북을 생성합니다.

[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19.2-61dafb.svg)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.2-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.4-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Azure Functions](https://img.shields.io/badge/Azure_Functions-1.24.0-0062ad.svg)](https://azure.microsoft.com/en-us/products/functions)

---

## 📑 목차

- [주요 기능](#-주요-기능)
- [시스템 아키텍처](#-시스템-아키텍처)
- [기술 스택](#-기술-스택)
- [시작하기](#-시작하기)
- [프로젝트 구조](#-프로젝트-구조)
- [API 문서](#-api-문서)
- [배포 환경](#-배포-환경)

---

## 🎯 주요 기능

### 1. 다양한 입력 소스 지원

- **문서 파일**: PDF, DOCX, TXT, PPTX
- **웹 페이지**: URL 크롤링
- **주 소스 + 보조 소스**: 메인 콘텐츠와 참고 자료 분리 (최대 4개)

### 2. AI 기반 스크립트 생성

- **LLM**: Google Vertex AI (Gemini 2.5 flash)
- **스타일 선택**: 강의형 / 대화형
- **난이도 설정**: 초급 / 중급 / 고급
- **자동 압축**: 목표 시간에 맞게 스크립트 조정

### 3. TTS 음성 생성

- **TTS**: Vertex AI Gemini TTS 2.5-flash-preview
- **다중 화자**: 진행자 / 게스트 역할 구분

### 4. 스트리밍 재생

- **HTTP Range Request**: 206 Partial Content 지원
- **실시간 진행 상황**: 세션 상태 실시간 추적
- **타임스탬프 스크립트**: 자막 형식 트랜스크립트 제공

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Client (Web/Mobile)                      │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────────┐
│          Azure Functions (HTTP Trigger) + FastAPI            │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Internal Auth  │  │  CORS MW     │  │  Alan Auth     │  │
│  │ Middleware     │  │              │  │  Service       │  │
│  └────────────────┘  └──────────────┘  └────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Routers: channels / sessions / streaming / health   │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ enqueue
┌────────────────────────▼────────────────────────────────────┐
│         Azure Queue Storage → Queue Trigger Worker           │
│                                                              │
│  Step 1: extract_ocr      → OCR + Vision (MetadataGenerator) │
│  Step 2: extract_finalize → 텍스트 구조화                    │
│  Step 3: script           → Vertex AI Gemini 스크립트 생성   │
│  Step 4: audio            → Google Cloud TTS 음성 합성       │
│  Step 5: finalize         → ffmpeg 병합 + 트랜스크립트       │
└───────┬──────────────────────────┬──────────────────────────┘
        │                          │
┌───────▼────────┐        ┌────────▼─────────────────────────┐
│  PostgreSQL    │        │    External Services (GCP)        │
│  - channels    │        │  - Vertex AI (Gemini 2.5 flash)   │
│  - sessions    │        │  - Vertex AI Gemini TTS           │
│  - inputs      │        │  - Google Cloud Speech            │
│  - prompt_     │        │                                   │
│    templates   │        │    Azure Blob Storage             │
└────────────────┘        │  - input_files/                   │
                          │  - pipeline/ (중간 결과)           │
                          │  - output_files/ (최종 결과)       │
                          └──────────────────────────────────┘
```

---

## 🛠️ 기술 스택

### Frontend

| 구분            | 기술           | 버전    | 비고              |
| --------------- | -------------- | ------- | ----------------- |
| 프레임워크      | React          | 19.2.0  | UI 라이브러리     |
| 언어            | TypeScript     | 5.9.3   | 타입 안정성       |
| 빌드 도구       | Vite           | 7.2.5   | rolldown-vite     |
| 라우팅          | React Router   | 7.9.6   | SPA 라우팅        |
| 스타일링        | Tailwind CSS   | 3.4.17  | 유틸리티 CSS      |
| HTTP 클라이언트 | fetch (native) | -       | 브라우저 내장     |
| 아이콘          | Lucide React   | 0.554.0 | 아이콘 라이브러리 |

### Backend

| 구분              | 기술                                              | 버전                           | 비고                      |
| ----------------- | ------------------------------------------------- | ------------------------------ | ------------------------- |
| 런타임            | Python                                            | 3.11+                          | 비동기 처리 지원          |
| 프레임워크        | FastAPI                                           | 0.121.2                        | REST API, 자동 문서화     |
| Functions 호스팅  | Azure Functions                                   | 1.24.0                         | HTTP + Queue Trigger      |
| 데이터베이스      | PostgreSQL                                        | 14+                            | 관계형 DB                 |
| ORM               | SQLAlchemy                                        | 2.0.46                         | 데이터베이스 추상화       |
| AI - LLM          | Vertex AI (Gemini)                                | google-genai 1.52.0            | 스크립트 생성             |
| AI - TTS          | Vertex AI (Gemini TTS) (Gemini 2.5-flash-preview) | google-cloud-aiplatform 1.75.0 | 음성 합성                 |
| AI - Vision       | Vertex AI Vision                                  | google-cloud-aiplatform 1.75.0 | 이미지 설명 생성          |
| AI 워크플로우     | LangGraph                                         | 1.0.4                          | 파이프라인 오케스트레이션 |
| AI 모니터링       | LangSmith                                         | 0.6.6                          | 파이프라인 트레이싱       |
| 파일 저장소       | Azure Blob Storage SDK                            | 12.28.0                        | 클라우드 스토리지         |
| 작업 큐           | Azure Queue Storage SDK                           | 12.15.0                        | 단계별 비동기 처리        |
| OCR               | rapidocr-onnxruntime                              | 1.4.4                          | 문자 인식 (한글/영어)     |
| 오디오 처리       | ffmpeg                                            | 수동 설치 (linux-x64)          | WAV→MP3 변환/병합         |
| 오디오 라이브러리 | pydub                                             | 0.25.1+                        | 오디오 길이 측정          |
| PDF 처리          | pdfplumber                                        | 0.11.4                         | 텍스트 추출               |
| HTTP 클라이언트   | httpx                                             | 0.28.1                         | Alan Auth 서버 호출       |

> Azure 배포 환경에서는 **LGPL 빌드(ffmpeg/ffprobe)** 를 사용하며, GitHub 파일 제한으로 인해 바이너리는 저장소에 포함되지 않습니다. (backend README 참고)

---

## 🚀 시작하기

### 필수 요구사항

**공통**

### 필수 요구사항

- Python 3.11+
- PostgreSQL 14+
- Google Cloud 프로젝트 (Vertex AI, Cloud TTS 활성화)
- Azure Storage 계정 (Blob + Queue) 또는 로컬 스토리지

> **ffmpeg**: GitHub 단일 파일 100MB 제한으로 바이너리는 저장소에 포함되지 않습니다.  
> Azure Functions 배포 시 `backend/app/bin/linux-x64/` 경로에 **직접 다운로드한 ffmpeg/ffprobe** 를 배치해야 합니다. (자세한 방법: `backend/README.md`)

---

### 1. 저장소 클론

```bash
git clone <repository-url>
cd ai-audiobook-generator
```

---

### 2. 백엔드 설정

#### 2.1. 의존성 설치

```bash
cd backend

# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

#### 2.2. 환경 변수 설정

`.env` 파일 생성:

```bash
# ===== 환경 구분 =====
ENVIRONMENT=development       # development | staging | production

# ===== 내부 서비스 인증 =====
INTERNAL_SERVICE_TOKEN=your-secret-token-here

# ===== Alan 사용자 인증 =====
AUTH_MODE=mock                # mock (개발) | real (운영)
ALAN_AUTH_BASE_URL=           # AUTH_MODE=real 일 때 필수
ACCESS_POLICY=all             # all | pro_only

# ===== Database =====
DATABASE_URL=postgresql://user:password@localhost:5432/audiobook
REPO_BACKEND=postgres         # postgres | memory

# ===== Storage =====
STORAGE_BACKEND=local         # local | azure
BASE_OUTPUT_DIR=./outputs
# AZURE_STORAGE_CONNECTION_STRING=...
# AZURE_STORAGE_CONTAINER=ai-audiobook

# ===== Azure Queue =====
# AZURE_STORAGE_QUEUE_NAME=ai-audiobook-jobs
# AzureWebJobsStorage=<connection-string>

# ===== Google Cloud =====
VERTEX_AI_PROJECT_ID=your-project-id
VERTEX_AI_REGION=asia-northeast3
VERTEX_AI_SERVICE_ACCOUNT_FILE=/tmp/gcp-sa.json
VERTEX_AI_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

#### 2.3. 데이터베이스 초기화

```bash
# PostgreSQL 데이터베이스 생성
createdb audiobook

# 테이블 생성
python -c "from app.db.models import Base; from app.db.db_session import engine; Base.metadata.create_all(engine)"
```

#### 2.4. 백엔드 실행

```bash
# 로컬 개발 서버 (HTTP만)
uvicorn app.main:app --reload --host 0.0.0.0 --port 4001

# Azure Functions 로컬 실행 (HTTP + Queue Trigger)
func start
```

서버 실행 후:

- API 서버: http://localhost:4001
- API 문서: http://localhost:4001/docs

---

### 3. 프론트엔드 설정

#### 3.1. 의존성 설치

```bash
cd frontend
npm install
```

#### 3.2. 환경 변수 설정

`.env` 파일 생성 (선택사항):

```bash
VITE_API_BASE_URL=http://localhost:4001
```

또는 `src/lib/api.ts`에서 직접 설정:

```typescript
export const API_BASE_URL = "http://localhost:4001";
```

#### 3.3. 프론트엔드 실행

```bash
# 개발 모드
npm run dev

# 빌드
npm run build

# 빌드 미리보기
npm run preview
```

개발 서버 실행 후:

- 프론트엔드: http://localhost:5173

---

## 📁 프로젝트 구조

```
ai-audiobook-generator/
├── frontend/                      # React 프론트엔드
│   ├── src/
│   │   ├── components/           # 공통 컴포넌트
│   │   │   ├── mobile/          # 모바일 UI 컴포넌트
│   │   │   └── Layout.tsx
│   │   ├── pages/               # 페이지 컴포넌트
│   │   │   ├── mobile/         # 모바일 페이지
│   │   │   └── ...
│   │   ├── lib/                # 유틸리티
│   │   └── App.tsx             # 라우팅 설정
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── backend/                       # FastAPI 백엔드
│   ├── app/
│   │   ├── routers/              # API 엔드포인트
│   │   │   ├── channels.py
│   │   │   ├── sessions.py
│   │   │   ├── streaming.py
│   │   │   └── health.py
│   │   ├── services/             # 비즈니스 로직
│   │   │   ├── session_service.py
│   │   │   ├── langgraph_service.py
│   │   │   └── storage_service.py
│   │   ├── repositories/         # 데이터 액세스
│   │   │   ├── interfaces/
│   │   │   ├── postgres/
│   │   │   └── memory/
│   │   ├── langgraph_pipeline/   # AI 워크플로우
│   │   │      └── podcast/
│   │   │          ├── graph.py          # LangGraph 노드 정의
│   │   │          ├── state.py
│   │   │          ├── document_converter_node.py  # 문서 변환
│   │   │          ├── metadata_generator_node.py  # OCR + Vision
│   │   │          ├── improved_hybrid_filter.py  # 이미지 필터링
│   │   │          ├── prompt_service.py # Prompt 템플릿 서비스
│   │   │          ├── script/           # 스크립트 노드 사용 모듈
│   │   │          ├── script_generator.py
│   │   │          ├── tail_focus_v5_fixed.py
│   │   │          ├── tts_service.py
│   │   │          ├── audio_processor.py
│   │   │          └── pricing.py
│   │   ├── middleware/           # 미들웨어
│   │   ├── db/                   # 데이터베이스
│   │   └── main.py              # 앱 진입점
│   ├── requirements.txt
│   └── .env
│
└── README.md                    # 이 파일
```

---

## 📚 API 문서

모든 요청(헬스체크 제외)에는 두 가지 인증이 필요합니다.

```bash
X-Internal-Service-Token: your-token
Authorization: Bearer <alan-token>   # 또는 alan_session_id 쿠키
```

> 개발 환경(`AUTH_MODE=mock`)에서는 Alan 인증 없이 동작합니다.

### 주요 엔드포인트

```bash
# 채널 생성
POST /v1/channels
Response: { channel_id, created_at }

# 채널 삭제
DELETE /v1/channels/{channel_id}

# 세션 생성 (파일 업로드 + 오디오북 생성 시작)
POST /v1/channels/{channel_id}/sessions
Body: multipart/form-data
  - files: File[] (pdf/docx/pptx/txt, 최대 4개)
  - links: JSON string array (URL 목록)
  - main_kind: "file" | "link"
  - main_index: int (0-based)
  - voice_id: string (default: "Fenrir")
  - style: "explain" | "lecture"
  - duration: int (분, default: 5)
  - difficulty: "basic" | "intermediate" | "advanced"
  - user_prompt: string

# 세션 조회 (폴링)
GET /v1/channels/{channel_id}/sessions/{session_id}

# 세션 목록
GET /v1/channels/{channel_id}/sessions

# 세션 삭제
DELETE /v1/channels/{channel_id}/sessions/{session_id}

# 오디오 스트리밍
GET /v1/channels/{channel_id}/files/audio/{session_id}/1
Header: Range: bytes=0-1023  (선택, 206 Partial Content 응답)
```

자세한 API 문서: http://localhost:4001/docs

---

## 📦 번들 리소스 및 설치 안내

Azure Functions 배포 환경 재현성을 위해 일부 리소스가 `backend/` 디렉토리에 포함되어 있습니다.

- **OCR 모델 파일**
  - 위치: `backend/ocr_model/`
  - 출처: https://huggingface.co/monkt/paddleocr-onnx/tree/main

- **FFmpeg (ffmpeg/ffprobe)**
  - 위치(배치 경로): `backend/app/bin/linux-x64/`
  - 출처: https://github.com/BtbN/FFmpeg-Builds/releases/tag/latest
  - 안내: GitHub 파일 제한(단일 100MB)으로 바이너리는 저장소에 포함되지 않으며, 수동 설치가 필요합니다.

자세한 설치/라이선스 및 동작 방식은 `backend/README.md`를 참고하세요.

---

## 🚢 배포 환경

**배포 명령**

```bash
func azure functionapp publish <function-app-name>
```

**운영 환경 체크리스트**

- `AUTH_MODE=real` 및 `ALAN_AUTH_BASE_URL` 설정
- `ACCESS_POLICY=pro_only` 설정 (Pro 전용 기능 활성화 시)
- `STORAGE_BACKEND=azure` 및 Azure 연결 문자열 설정
- `REPO_BACKEND=postgres` 및 `DATABASE_URL` 설정
- `VERTEX_AI_SERVICE_ACCOUNT_JSON` 환경변수 설정

```

```

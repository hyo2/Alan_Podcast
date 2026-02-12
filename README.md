# AI Audiobook Generator (Alan Pods)

> AI 기반 자동 오디오북 생성 시스템  
> 문서를 업로드하면 자동으로 팟캐스트 형식의 오디오북을 생성합니다.

[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19.2-61dafb.svg)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688.svg)](https://fastapi.tiangolo.com/)

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
│                     Client (React + Vite)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ Mobile UI   │  │ Web UI      │  │ Audio Player     │    │
│  └─────────────┘  └─────────────┘  └──────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────────┐
│                  API Gateway (FastAPI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Auth MW      │  │ CORS MW      │  │ Routers      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Service Layer                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SessionService → LangGraphService (6 Nodes)         │   │
│  │  1. extract_texts → 2. combine_texts                 │   │
│  │  3. generate_script → 4. generate_audio              │   │
│  │  5. merge_audio → 6. generate_transcript             │   │
│  └──────────────────────────────────────────────────────┘   │
└───────┬──────────────────────────┬──────────────────────────┘
        │                          │
┌───────▼────────┐        ┌────────▼─────────────────────────┐
│  PostgreSQL    │        │    External Services             │
│  - channels    │        │  - Vertex AI (Gemini 2.5 flash)  │
│  - sessions    │        │  - Google Cloud Speech           │
│  - inputs      │        │  - Azure Blob Storage            │
└────────────────┘        └──────────────────────────────────┘
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

| 구분          | 기술                   | 버전              | 비고                      |
| ------------- | ---------------------- | ----------------- | ------------------------- |
| 런타임        | Python                 | 3.11+             | 비동기 처리 지원          |
| 프레임워크    | FastAPI                | latest            | REST API                  |
| 데이터베이스  | PostgreSQL             | 14+               | 관계형 DB                 |
| ORM           | SQLAlchemy             | 2.x               | 데이터베이스 추상화       |
| AI - LLM      | Vertex AI (Gemini)     | 2.5 flash         | 스크립트 생성             |
| AI - TTS      | Vertex AI (Gemini TTS) | 2.5-flash-preview | 음성 생성                 |
| AI 워크플로우 | LangGraph              | latest            | 파이프라인 오케스트레이션 |
| 파일 저장소   | Azure Blob Storage     | SDK 12.x          | 클라우드 스토리지         |
| 오디오 처리   | FFmpeg                 | 4.x+              | 변환 및 병합              |

---

## 🚀 시작하기

### 필수 요구사항

**공통**

- Node.js 18+
- Python 3.11+
- FFmpeg 4.x+
- PostgreSQL 14+

**외부 서비스**

- Google Cloud 프로젝트 (Vertex AI, Cloud TTS 활성화)
- Azure Storage 계정 (또는 로컬 스토리지 사용)

---

### 1. 저장소 클론

```bash
git clone <repository-url>
cd ai-audiobook-generator
```

---

### 2. 백엔드 설정

#### 2.1. 의존성 설치

````bash
cd backend

# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt


#### 2.2. 환경 변수 설정

`.env` 파일 생성:

```bash
# ===== 환경 구분 =====
ENVIRONMENT=development

# ===== 내부 서비스 인증 =====
INTERNAL_SERVICE_TOKEN=your-secret-token-here

# ===== 서버 설정 =====
PORT=4001
LOG_LEVEL=INFO

# ===== CORS 설정 =====
# development: 빈 값 (코드에서 * 사용)
# staging/production: 허용할 origin (콤마 구분)
CORS_ORIGINS=

# ===== Vertex AI (Google Cloud) =====
VERTEX_AI_PROJECT_ID=your-project-id
VERTEX_AI_REGION=us-central1
VERTEX_AI_SERVICE_ACCOUNT_FILE=path/to/service-account.json
VERTEX_AI_MODEL_TEXT=gemini-2.5-flash

# ===== 데이터베이스 =====
# PostgreSQL 연결
DATABASE_URL=postgresql://user:password@host:5432/database
# 저장소 백엔드 - memory/postgres
REPO_BACKEND=postgres

# ===== 스토리지 =====
# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER=alan-files

# Azure Storage Queue
AZURE_STORAGE_QUEUE_NAME=ai-audiobook-jobs
FUNCTIONS_WORKER_RUNTIME=python
AzureWebJobsStorage=your-connection-string

# 스토리지 백엔드 - azure/local
STORAGE_BACKEND=azure

# 출력 디렉토리 (로컬 모드)
BASE_OUTPUT_DIR=./outputs

# 프론트엔드 URL
FRONTEND_URL=http://localhost:5173
````

#### 2.3. 데이터베이스 초기화

```bash
# PostgreSQL 데이터베이스 생성
createdb audiobook

# 테이블 생성
python -c "from app.db.models import Base; from app.db.db_session import engine; Base.metadata.create_all(engine)"
```

#### 2.4. 백엔드 실행

```bash
# 개발 모드
uvicorn app.main:app --reload --host 0.0.0.0 --port 4001

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
│   │   │   ├── postgres/
│   │   │   └── memory/
│   │   ├── langgraph_pipeline/   # AI 워크플로우
│   │   │   └── podcast/
│   │   │       ├── graph.py
│   │   │       ├── state.py
│   │   │       ├── script_generator.py
│   │   │       ├── tts_service.py
│   │   │       └── audio_processor.py
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

### 주요 엔드포인트

#### 채널 관리

```bash
# 채널 생성
POST /v1/channels
Response: { channel_id, created_at }

# 채널 삭제
DELETE /v1/channels/{channel_id}
```

#### 세션 관리

```bash
# 세션 생성
POST /v1/channels/{channel_id}/sessions
Body: {
  "options": {
    "host1": "TTS 목소리명",
    "host2": "",
    "style": "explain",      # explain | lecture
    "duration": 5,           # 5분 | 10분 | 15분
    "difficulty": "intermediate"  # basic | intermediate | advanced
  }
}

# 세션 조회
GET /v1/channels/{channel_id}/sessions/{session_id}

# 세션 삭제
DELETE /v1/channels/{channel_id}/sessions/{session_id}
```

#### 파일 업로드

```bash
# 파일 업로드
POST /v1/channels/{channel_id}/sessions/{session_id}/inputs
Body: multipart/form-data
  - file: 파일
  - role: main | aux
```

#### 오디오 스트리밍

```bash
# 오디오 스트리밍
GET /v1/channels/{channel_id}/files/audio/{session_id}/1

# Range 헤더 지원
Header: Range: bytes=0-1023
Response: 206 Partial Content
```

자세한 API 문서: http://localhost:4001/docs (Swagger UI)

## 🔧 개발 가이드

### 코드 스타일

**Frontend**

```bash
# 린트 검사
npm run lint

# 타입 체크
npm run build
```

**Backend**

```bash
# 코드 포맷팅
black app/

# 타입 체크
mypy app/
```

### 테스트

```bash
# Backend
pytest tests/

# Frontend
npm test
```

---

## 🐛 트러블슈팅

### FFmpeg 관련 에러

```bash
# 설치 확인
ffmpeg -version

# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

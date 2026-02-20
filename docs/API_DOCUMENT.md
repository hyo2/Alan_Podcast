# AI Audiobook API 문서

> **관련 문서**: [에러 코드](./ERROR_CODES.md) | [TypeScript 가이드](./TYPESCRIPT.md)

---

## 목차

1. [개요](#개요)
2. [인증](#인증)
3. [헬스체크](#헬스체크)
4. [채널 관리](#채널-관리)
5. [세션 관리](#세션-관리)
6. [오디오 스트리밍](#오디오-스트리밍)

---

## 개요

AI Audiobook API는 문서를 교육용 팟캐스트 스타일 오디오북으로 변환하는 서비스입니다.

### 응답 형식

모든 API는 다음과 같은 일관된 형식으로 응답합니다:

**성공 응답**

```json
{
  "success": true,
  "data": {
    /* 응답 데이터 */
  },
  "message": "optional message"
}
```

**에러 응답**

```json
{
  "success": false,
  "data": null,
  "message": "에러 메시지",
  "error_code": "ERROR_CODE"
}
```

> 에러 코드 상세 설명은 [에러 코드 문서](./ERROR_CODES.md)를 참고하세요.

---

## 인증

### 내부 서비스 토큰

모든 API 요청(헬스체크 제외)에는 내부 서비스 토큰이 필요합니다.

**헤더**

```
X-Internal-Service-Token: <your-token>
```

**인증 실패 시**

- **Status Code**: `401 Unauthorized`
- **Error Code**: `UNAUTHORIZED`
- **Message**: "Invalid or missing authentication token"

**인증 제외 경로**

- `/v1/health`
- `/docs`
- `/openapi.json`

---

### Alan 사용자 인증

내부 서비스 토큰 검증 이후, Alan 사용자 인증이 추가로 수행됩니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

> 쿠키(`alan_session_id` 또는 `alan_guest_token`)로도 Alan 인증 대체 가능

**인증 방법 (우선순위 순)**

1. 쿠키: `alan_session_id`
2. 쿠키: `alan_guest_token`
3. 헤더: `Authorization: Bearer <token>`

**인증 실패 시**

- **Status Code**: `401 Unauthorized`
- **Error Code**: `UNAUTHORIZED`
- **Message**: "인증 토큰이 누락되었습니다" 또는 "유효하지 않은 인증 토큰입니다"

**인증 서버 오류 시**

- **Status Code**: `502 Bad Gateway`
- **Message**: "인증 서비스에 연결할 수 없습니다" 또는 "인증 서비스 응답 시간 초과"

**접근 정책 (ACCESS_POLICY)**

| 정책         | 동작                                                                               |
| ------------ | ---------------------------------------------------------------------------------- |
| `all` (기본) | 인증만 통과하면 모든 사용자 허용                                                   |
| `pro_only`   | Pro 역할(`pro_user`, `internal_user`, `pro_user_promotion`)만 허용, 그 외 403 반환 |

> **개발 환경**: `AUTH_MODE=mock` 설정 시 Alan 인증 없이 Pro 사용자로 처리됩니다. 현재 mock 환경 기준으로 검증되었으며, 실제 Alan Auth 연동은 운영 배포 시 확인이 필요합니다.

---

## API 엔드포인트 목록

| 메서드   | 엔드포인트                                                     | 설명                                                                    | 인증 필요 |
| -------- | -------------------------------------------------------------- | ----------------------------------------------------------------------- | --------- |
| `GET`    | `/v1/health`                                                   | [헬스체크](#헬스체크)                                                   | ❌        |
| `POST`   | `/v1/channels`                                                 | [채널 생성](#post-v1channels)                                           | ✅        |
| `DELETE` | `/v1/channels/{channel_id}`                                    | [채널 삭제](#delete-v1channelschannel_id)                               | ✅        |
| `POST`   | `/v1/channels/{channel_id}/sessions`                           | [세션 생성](#post-v1channelschannel_idsessions)                         | ✅        |
| `GET`    | `/v1/channels/{channel_id}/sessions/{session_id}`              | [세션 조회](#get-v1channelschannel_idsessionssession_id)                | ✅        |
| `GET`    | `/v1/channels/{channel_id}/sessions`                           | [세션 목록 조회](#get-v1channelschannel_idsessions)                     | ✅        |
| `DELETE` | `/v1/channels/{channel_id}/sessions/{session_id}`              | [세션 삭제](#delete-v1channelschannel_idsessionssession_id)             | ✅        |
| `GET`    | `/v1/channels/{channel_id}/files/audio/{session_id}/{chapter}` | [오디오 스트리밍](#get-v1channelschannel_idfilesaudiosession_idchapter) | ✅        |

---

## 헬스체크

### `GET /v1/health`

서비스 상태를 확인합니다.

**요청 예시**

```bash
curl -X GET "http://localhost:4001/v1/health"
```

**응답 예시** (200 OK)

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "service": "ai-audiobook"
  },
  "message": null
}
```

---

## 채널 관리

채널은 세션들을 그룹화하는 최상위 컨테이너입니다.

### `POST /v1/channels`

새 채널을 생성합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

**요청 예시**

```bash
curl -X POST "http://localhost:4001/v1/channels" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token"
```

**응답 예시** (201 Created)

```json
{
  "success": true,
  "data": {
    "channel_id": "ch_abc123xyz",
    "created_at": "2025-02-03T10:30:00Z"
  },
  "message": null
}
```

**에러 응답**

- `401 UNAUTHORIZED`: 인증 실패
- `500 INTERNAL_ERROR`: 서버 내부 오류

---

### `DELETE /v1/channels/{channel_id}`

채널과 관련된 모든 세션 및 파일을 삭제합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID

**요청 예시**

```bash
curl -X DELETE "http://localhost:4001/v1/channels/ch_abc123xyz" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token"
```

**응답 예시** (200 OK)

```json
{
  "success": true,
  "data": null,
  "message": "Channel deleted"
}
```

**에러 응답**

- `401 UNAUTHORIZED`: 인증 실패
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음
- `500 INTERNAL_ERROR`: 서버 내부 오류

---

## 세션 관리

세션은 오디오북 생성 작업 단위입니다.

### `POST /v1/channels/{channel_id}/sessions`

새 세션을 생성하고 오디오북 생성을 시작합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
Content-Type: multipart/form-data
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID

**Form Data**

| 필드          | 타입    | 필수   | 기본값           | 설명                                                   |
| ------------- | ------- | ------ | ---------------- | ------------------------------------------------------ |
| `files`       | File[]  | 조건부 | -                | 업로드 파일 (최대 4개, pdf/docx/pptx/txt)              |
| `links`       | string  | 조건부 | `"[]"`           | URL 배열 JSON 문자열 (최대 4개)                        |
| `main_kind`   | string  | 필수   | -                | 주 강의자료 유형 (`"file"` 또는 `"link"`)              |
| `main_index`  | integer | 필수   | -                | 주 강의자료 인덱스 (0-based)                           |
| `voice_id`    | string  | 선택   | `"Fenrir"`       | 음성 ID (Gemini TTS 제공 음성 이름)                    |
| `style`       | string  | 선택   | `"explain"`      | 스타일 (`"lecture"` \| `"explain"`)                    |
| `duration`    | integer | 선택   | `5`              | 목표 길이 (분)                                         |
| `difficulty`  | string  | 선택   | `"intermediate"` | 난이도 (`"basic"` \| `"intermediate"` \| `"advanced"`) |
| `user_prompt` | string  | 선택   | `""`             | 사용자 커스텀 프롬프트                                 |

**입력 제약사항**

- `files`와 `links` 중 최소 1개 이상 필요
- 전체 입력(파일 + 링크) 최대 4개
- `main_kind="file"`인 경우: `main_index`는 files 배열 범위 내
- `main_kind="link"`인 경우: `main_index`는 links 배열 범위 내

**요청 예시**

```bash
curl -X POST "http://localhost:4001/v1/channels/ch_abc123xyz/sessions" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token" \
  -F "files=@document.pdf" \
  -F "files=@slides.pptx" \
  -F 'links=["https://example.com/article"]' \
  -F "main_kind=file" \
  -F "main_index=0" \
  -F "voice_id=Fenrir" \
  -F "style=lecture" \
  -F "duration=5" \
  -F "difficulty=intermediate" \
  -F "user_prompt=간략하게 설명해주세요"
```

**응답 예시** (201 Created)

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz789abc",
    "status": "processing",
    "progress": 0,
    "current_step": "파일 업로드 완료 및 변환 시작",
    "created_at": "2025-02-03T10:35:00Z"
  },
  "message": null
}
```

**에러 응답**

- `400 INVALID_FILE_FORMAT`: 잘못된 파일 형식, links 파싱 실패, 입력 개수 초과, main 지정 오류
- `401 UNAUTHORIZED`: 인증 실패
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음
- `500 INTERNAL_ERROR`: 서버 내부 오류, 큐 등록 실패

> 에러 코드 상세 설명은 [에러 코드 문서](./ERROR_CODES.md)를 참고하세요.

---

### `GET /v1/channels/{channel_id}/sessions/{session_id}`

특정 세션의 상세 정보를 조회합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID
- `session_id` (string, required): 세션 ID

**요청 예시**

```bash
curl -X GET "http://localhost:4001/v1/channels/ch_abc123xyz/sessions/sess_xyz789abc" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token"
```

**응답 예시 - 처리 중** (200 OK)

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz789abc",
    "status": "processing",
    "progress": 60,
    "current_step": "script_complete",
    "result": null,
    "error": null,
    "created_at": "2025-02-03T10:35:00Z"
  },
  "message": null
}
```

**응답 예시 - 완료** (200 OK)

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz789abc",
    "status": "completed",
    "progress": 100,
    "current_step": "completed",
    "result": {
      "chapters": [
        {
          "chapter": 1,
          "title": "AI와 머신러닝의 기초",
          "duration": 597.5
        }
      ],
      "total_duration": 597.5
    },
    "error": null,
    "created_at": "2025-02-03T10:35:00Z"
  },
  "message": null
}
```

**응답 예시 - 실패** (200 OK)

```json
{
  "success": true,
  "data": {
    "session_id": "sess_xyz789abc",
    "status": "failed",
    "progress": -1,
    "current_step": "error",
    "result": null,
    "error": "스크립트 생성 중 오류 발생",
    "created_at": "2025-02-03T10:35:00Z"
  },
  "message": null
}
```

**진행 상태 매핑**

| current_step                    | progress | 설명               |
| ------------------------------- | -------- | ------------------ |
| `start`                         | 0        | 시작               |
| `파일 업로드 시작`              | 5        | 파일 업로드 시작   |
| `파일 업로드 완료 및 변환 시작` | 10       | 파일 업로드 완료   |
| `extract_complete`              | 30       | 텍스트 추출 완료   |
| `combine_complete`              | 40       | 콘텐츠 결합 완료   |
| `script_complete`               | 60       | 스크립트 생성 완료 |
| `audio_complete`                | 80       | 오디오 합성 완료   |
| `merge_complete`                | 90       | 오디오 병합 완료   |
| `completed`                     | 100      | 전체 완료          |
| `error`                         | -1       | 오류 발생          |

**에러 응답**

- `401 UNAUTHORIZED`: 인증 실패
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음
- `404 SESSION_NOT_FOUND`: 세션을 찾을 수 없음

---

### `GET /v1/channels/{channel_id}/sessions`

채널의 모든 세션 목록을 조회합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID

**쿼리 파라미터**

- `limit` (integer, optional, default=50): 한 번에 가져올 세션 수
- `offset` (integer, optional, default=0): 건너뛸 세션 수

**요청 예시**

```bash
curl -X GET "http://localhost:4001/v1/channels/ch_abc123xyz/sessions?limit=20&offset=0" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token"
```

**응답 예시** (200 OK)

```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": "sess_xyz789abc",
        "status": "completed",
        "progress": 100,
        "created_at": "2025-02-03T10:35:00Z"
      },
      {
        "session_id": "sess_def456ghi",
        "status": "processing",
        "progress": 60,
        "created_at": "2025-02-03T09:20:00Z"
      }
    ],
    "total": 2
  },
  "message": null
}
```

**에러 응답**

- `401 UNAUTHORIZED`: 인증 실패
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음

---

### `DELETE /v1/channels/{channel_id}/sessions/{session_id}`

특정 세션과 관련 파일을 삭제합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID
- `session_id` (string, required): 세션 ID

**요청 예시**

```bash
curl -X DELETE "http://localhost:4001/v1/channels/ch_abc123xyz/sessions/sess_xyz789abc" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token"
```

**응답 예시** (200 OK)

```json
{
  "success": true,
  "data": null,
  "message": "Session deleted"
}
```

**에러 응답**

- `401 UNAUTHORIZED`: 인증 실패
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음
- `404 SESSION_NOT_FOUND`: 세션을 찾을 수 없음
- `500 INTERNAL_ERROR`: 서버 내부 오류

---

## 오디오 스트리밍

### `GET /v1/channels/{channel_id}/files/audio/{session_id}/{chapter}`

생성된 오디오 파일을 스트리밍합니다. Range 요청을 지원합니다.

**요청 헤더**

```
X-Internal-Service-Token: <your-token>
Authorization: Bearer <alan-token>
Range: bytes=0-1023  (선택사항)
```

**경로 파라미터**

- `channel_id` (string, required): 채널 ID
- `session_id` (string, required): 세션 ID
- `chapter` (integer, required): 챕터 번호
  - **현재는 `1`만 지원**
  - 결과 오디오 파일 1개로 제공하기 때문(챕터 기능 미제공)

**요청 예시**

전체 다운로드:

```bash
curl -X GET "http://localhost:4001/v1/channels/ch_abc123xyz/files/audio/sess_xyz789abc/1" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token" \
  --output audio.mp3
```

Range 요청:

```bash
curl -X GET "http://localhost:4001/v1/channels/ch_abc123xyz/files/audio/sess_xyz789abc/1" \
  -H "X-Internal-Service-Token: your-token" \
  -H "Authorization: Bearer your-alan-token" \
  -H "Range: bytes=0-1023" \
  --output audio_chunk.mp3
```

**응답 헤더 - 전체 응답** (200 OK)

```
Content-Type: audio/mpeg
Content-Length: 5242880
Accept-Ranges: bytes
```

**응답 헤더 - Partial Content** (206 Partial Content)

```
Content-Type: audio/mpeg
Content-Range: bytes 0-1023/5242880
Content-Length: 1024
Accept-Ranges: bytes
```

**에러 응답**

- `400 PROCESSING_FAILED`: 처리가 완료되지 않음 (status != `"completed"`)
- `401 UNAUTHORIZED`: 인증 실패
- `404 NOT_FOUND`: 챕터를 찾을 수 없음 (현재 chapter=1만 지원)
- `404 CHANNEL_NOT_FOUND`: 채널을 찾을 수 없음
- `404 SESSION_NOT_FOUND`: 세션을 찾을 수 없음
- `416 Range Not Satisfiable`: 잘못된 Range 요청
- `500 INTERNAL_ERROR`: 파일 읽기 실패

**Range 요청 형식**

- `bytes=<start>-<end>`: 특정 바이트 범위
- `bytes=<start>-`: start부터 끝까지
- `bytes=-<N>`: 마지막 N바이트
- 예시: `Range: bytes=0-1023`, `Range: bytes=1024-`, `Range: bytes=-2048`

---

## 변경 이력

### v1.1.0 (2025-02-20)

- Alan 사용자 인증 섹션 추가
- 전 엔드포인트 요청 헤더에 `Authorization: Bearer` 추가
- 전 엔드포인트 에러 응답에 `401 UNAUTHORIZED` 추가

### v1.0.0 (2025-02-03)

- 초기 API 문서 작성
- 채널, 세션, 오디오 스트리밍 엔드포인트 정의

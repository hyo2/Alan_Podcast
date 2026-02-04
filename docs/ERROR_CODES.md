# 에러 코드 가이드

> **관련 문서**: [API 문서](./API.md) | [TypeScript 가이드](./TYPESCRIPT.md)

---

## 목차

1. [에러 응답 형식](#에러-응답-형식)
2. [에러 코드 목록](#에러-코드-목록)
3. [에러 코드별 상세 설명](#에러-코드별-상세-설명)
4. [에러 응답 예시](#에러-응답-예시)

---

## 에러 응답 형식

모든 에러 응답은 다음과 같은 일관된 형식을 따릅니다:

```json
{
  "success": false,
  "data": null,
  "message": "구체적인 에러 메시지",
  "error_code": "ERROR_CODE"
}
```

**필드 설명**

- `success`: 항상 `false`
- `data`: 항상 `null`
- `message`: 에러 메시지
- `error_code`: 에러 타입을 구분하는 코드 (대문자 영문, 언더스코어)

---

## 에러 코드 목록

| 에러 코드             | HTTP 상태 | 설명                                |
| --------------------- | --------- | ----------------------------------- |
| `UNAUTHORIZED`        | 401       | 인증 실패                           |
| `INVALID_FILE_FORMAT` | 400       | 잘못된 파일 형식 또는 요청 파라미터 |
| `CHANNEL_NOT_FOUND`   | 404       | 채널을 찾을 수 없음                 |
| `SESSION_NOT_FOUND`   | 404       | 세션을 찾을 수 없음                 |
| `NOT_FOUND`           | 404       | 일반 리소스를 찾을 수 없음          |
| `PROCESSING_FAILED`   | 400       | 처리 중 오류 또는 미완료 상태       |
| `INTERNAL_ERROR`      | 500       | 서버 내부 오류                      |

---

## 에러 코드별 상세 설명

### `UNAUTHORIZED` (401)

**의미**: 인증 실패

**발생 조건**

- `X-Internal-Service-Token` 헤더가 누락됨
- 토큰 값이 서버의 설정값과 일치하지 않음

**발생 API**

- 헬스체크(`/v1/health`)를 제외한 **모든 API**

**클라이언트 대응**

- 토큰이 올바르게 설정되었는지 확인
- 환경 변수 또는 설정 파일에서 토큰 값 재확인
- 401 응답 시 로그인 또는 인증 플로우로 리다이렉트 (필요 시)

**예시 메시지**

```
"Invalid or missing authentication token"
```

---

### `INVALID_FILE_FORMAT` (400)

**의미**: 잘못된 파일 형식 또는 요청 파라미터 오류

**발생 조건**

1. 지원하지 않는 파일 확장자 업로드 (pdf/docx/pptx/txt 외)
2. `links` 파라미터 JSON 파싱 실패
3. 파일과 링크가 모두 비어있음
4. 입력 개수 4개 초과 (파일 + 링크 합계)
5. `main_kind` 값이 `"file"` 또는 `"link"`가 아님
6. `main_index`가 배열 범위를 초과함

**발생 API**

- `POST /v1/channels/{channel_id}/sessions` (세션 생성)

**클라이언트 대응**

- 파일 확장자 검증 로직 추가
- JSON 문자열 형식 확인
- 입력 개수 제한 검증
- main_kind와 main_index 유효성 검사

**예시 메시지**

```
"지원하지 않는 파일 형식입니다: document.exe (pdf, docx, pptx, txt만 가능)"
"links 파싱에 실패했습니다. JSON 배열 문자열인지 확인하세요."
"입력은 최대 4개까지 가능합니다. (현재 5개)"
"main_kind는 'file' 또는 'link' 여야 합니다."
"main_index 범위가 올바르지 않습니다. files 길이=2, main_index=3"
```

---

### `CHANNEL_NOT_FOUND` (404)

**의미**: 요청한 채널을 찾을 수 없음

**발생 조건**

- 존재하지 않는 `channel_id`로 요청
- 이미 삭제된 채널에 접근 시도

**발생 API**

- `DELETE /v1/channels/{channel_id}`
- `POST /v1/channels/{channel_id}/sessions`
- `GET /v1/channels/{channel_id}/sessions/{session_id}`
- `GET /v1/channels/{channel_id}/sessions`
- `DELETE /v1/channels/{channel_id}/sessions/{session_id}`
- `GET /v1/channels/{channel_id}/files/audio/{session_id}/{chapter}`

**클라이언트 대응**

- 채널 ID가 올바른지 확인
- 채널이 삭제되었을 수 있으므로 채널 목록 새로고침
- 404 응답 시 "채널을 찾을 수 없습니다" 메시지 표시

**예시 메시지**

```
"요청하신 채널을 찾을 수 없습니다."
```

---

### `SESSION_NOT_FOUND` (404)

**의미**: 요청한 세션을 찾을 수 없음

**발생 조건**

- 존재하지 않는 `session_id`로 요청
- 다른 채널의 세션에 접근 시도 (channel_id 불일치)
- 이미 삭제된 세션에 접근 시도

**발생 API**

- `GET /v1/channels/{channel_id}/sessions/{session_id}`
- `DELETE /v1/channels/{channel_id}/sessions/{session_id}`
- `GET /v1/channels/{channel_id}/files/audio/{session_id}/{chapter}`

**클라이언트 대응**

- 세션 ID가 올바른지 확인
- channel_id와 session_id 매핑이 올바른지 확인
- 세션이 삭제되었을 수 있으므로 세션 목록 새로고침
- 404 응답 시 "세션을 찾을 수 없습니다" 메시지 표시

**예시 메시지**

```
"요청하신 세션을 찾을 수 없습니다."
```

---

### `NOT_FOUND` (404)

**의미**: 일반 리소스를 찾을 수 없음

**발생 조건**

- 지원하지 않는 챕터 번호 요청 (현재 chapter=1만 지원)

**발생 API**

- `GET /v1/channels/{channel_id}/files/audio/{session_id}/{chapter}`

**클라이언트 대응**

- 현재는 chapter 파라미터를 항상 `1`로 고정
- 향후 다중 챕터 지원 시 유효한 챕터 범위 확인

**예시 메시지**

```
"챕터를 찾을 수 없습니다."
```

---

### `PROCESSING_FAILED` (400)

**의미**: 처리가 실패했거나 아직 완료되지 않음

**발생 조건**

- 세션 상태가 `"completed"`가 아닌데 오디오 스트리밍 요청
- 세션이 `"processing"` 또는 `"failed"` 상태

**발생 API**

- `GET /v1/channels/{channel_id}/files/audio/{session_id}/{chapter}`

**클라이언트 대응**

- 세션 상태를 먼저 조회(`GET /v1/channels/{channel_id}/sessions/{session_id}`)
- `status === "completed"`일 때만 오디오 스트리밍 시도
- `status === "processing"`이면 폴링 계속
- `status === "failed"`이면 에러 메시지 표시

**예시 메시지**

```
"처리가 완료되지 않았습니다."
```

---

### `INTERNAL_ERROR` (500)

**의미**: 서버 내부 오류

**발생 조건**

- 예상치 못한 서버 오류
- 데이터베이스 연결 실패
- 스토리지(Azure Blob) 접근 실패
- 큐(Azure Queue) 등록 실패
- 완료 상태인데 오디오 파일 정보가 누락됨 (audio_key 없음)

**발생 API**

- 모든 API에서 발생 가능

**클라이언트 대응**

- 일시적 오류일 수 있으므로 재시도 로직 구현 (exponential backoff 권장)
- 재시도 후에도 실패하면 "서버 오류가 발생했습니다" 메시지 표시
- 에러 로그를 서버에 전송하거나 개발팀에 알림

**예시 메시지**

```
"서버 내부 오류: <구체적인 오류 내용>"
"작업 큐 등록에 실패했습니다: Connection timeout"
"완료된 세션의 오디오 파일 정보를 찾을 수 없습니다."
"파일 읽기 실패"
```

---

## 에러 응답 예시

### 401 Unauthorized

```json
{
  "success": false,
  "data": null,
  "message": "Invalid or missing authentication token",
  "error_code": "UNAUTHORIZED"
}
```

---

### 400 Invalid File Format

```json
{
  "success": false,
  "data": null,
  "message": "지원하지 않는 파일 형식입니다: document.exe (pdf, docx, pptx, txt만 가능)",
  "error_code": "INVALID_FILE_FORMAT"
}
```

```json
{
  "success": false,
  "data": null,
  "message": "입력은 최대 4개까지 가능합니다. (현재 5개)",
  "error_code": "INVALID_FILE_FORMAT"
}
```

---

### 404 Channel Not Found

```json
{
  "success": false,
  "data": null,
  "message": "요청하신 채널을 찾을 수 없습니다.",
  "error_code": "CHANNEL_NOT_FOUND"
}
```

---

### 404 Session Not Found

```json
{
  "success": false,
  "data": null,
  "message": "요청하신 세션을 찾을 수 없습니다.",
  "error_code": "SESSION_NOT_FOUND"
}
```

---

### 404 Not Found

```json
{
  "success": false,
  "data": null,
  "message": "챕터를 찾을 수 없습니다.",
  "error_code": "NOT_FOUND"
}
```

---

### 400 Processing Failed

```json
{
  "success": false,
  "data": null,
  "message": "처리가 완료되지 않았습니다.",
  "error_code": "PROCESSING_FAILED"
}
```

---

### 500 Internal Error

```json
{
  "success": false,
  "data": null,
  "message": "작업 큐 등록에 실패했습니다: Connection timeout",
  "error_code": "INTERNAL_ERROR"
}
```

```json
{
  "success": false,
  "data": null,
  "message": "서버 내부 오류: Database connection failed",
  "error_code": "INTERNAL_ERROR"
}
```

---

## 에러 처리 권장 패턴

### TypeScript 예시

```typescript
async function handleApiCall<T>(
  apiCall: () => Promise<ApiResponse<T>>,
): Promise<T | null> {
  try {
    const response = await apiCall();

    if (response.success) {
      return response.data;
    }

    // 에러 코드별 처리
    switch (response.error_code) {
      case "UNAUTHORIZED":
        // 인증 실패 -> 로그인 페이지로 리다이렉트
        window.location.href = "/login";
        break;

      case "CHANNEL_NOT_FOUND":
      case "SESSION_NOT_FOUND":
        // 리소스 없음 -> 목록 새로고침 후 메시지 표시
        alert(response.message);
        refreshList();
        break;

      case "PROCESSING_FAILED":
        // 처리 미완료 -> 세션 상태 확인 안내
        alert(
          "세션 처리가 아직 완료되지 않았습니다. 잠시 후 다시 시도해주세요.",
        );
        break;

      case "INVALID_FILE_FORMAT":
        // 입력 오류 -> 사용자에게 구체적 오류 표시
        alert(response.message);
        break;

      case "INTERNAL_ERROR":
        // 서버 오류 -> 재시도 또는 고객센터 안내
        if (confirm("서버 오류가 발생했습니다. 다시 시도하시겠습니까?")) {
          return handleApiCall(apiCall); // 재시도
        }
        break;

      default:
        // 알 수 없는 오류
        alert("알 수 없는 오류가 발생했습니다.");
    }

    return null;
  } catch (error) {
    // 네트워크 오류 등
    console.error("API 호출 실패:", error);
    alert("네트워크 오류가 발생했습니다. 인터넷 연결을 확인해주세요.");
    return null;
  }
}
```

---

## 변경 이력

### v1.0.0 (2025-02-03)

- 초기 에러 코드 문서 작성
- 7개 에러 코드 정의 및 상세 설명
- 에러 처리 권장 패턴 추가

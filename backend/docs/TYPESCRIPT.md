# TypeScript 가이드

> **관련 문서**: [API 문서](./API.md) | [에러 코드](./ERROR_CODES.md)

---

## 목차

1. [타입 정의](#타입-정의)
2. [API 클라이언트](#api-클라이언트)
3. [사용 예시](#사용-예시)
4. [폴링 패턴](#폴링-패턴)

---

## 타입 정의

### 공통 타입

```typescript
// API 공통 응답 타입
interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  message?: string;
  error_code?: string;
}

// 에러 코드 타입
type ErrorCode =
  | "UNAUTHORIZED"
  | "NOT_FOUND"
  | "CHANNEL_NOT_FOUND"
  | "SESSION_NOT_FOUND"
  | "INVALID_FILE_FORMAT"
  | "PROCESSING_FAILED"
  | "INTERNAL_ERROR";
```

---

### 채널 타입

```typescript
interface Channel {
  channel_id: string;
  created_at: string; // ISO 8601 format (UTC with Z suffix)
}
```

---

### 세션 타입

```typescript
// 세션 상태
type SessionStatus = "processing" | "completed" | "failed";

// 진행 단계
type CurrentStep =
  | "start"
  | "파일 업로드 시작"
  | "파일 업로드 완료 및 변환 시작"
  | "extract_complete"
  | "combine_complete"
  | "script_complete"
  | "audio_complete"
  | "merge_complete"
  | "completed"
  | "error";

// 챕터 정보
interface Chapter {
  chapter: number;
  title: string;
  duration: number; // 초 단위
}

// 세션 결과
interface SessionResult {
  chapters: Chapter[];
  total_duration: number; // 초 단위
}

// 세션 상세 정보
interface SessionDetail {
  session_id: string;
  status: SessionStatus;
  progress: number; // -1 (에러) 또는 0-100
  current_step: CurrentStep;
  result: SessionResult | null;
  error: string | null;
  created_at: string; // ISO 8601 format
}

// 세션 목록 아이템
interface SessionListItem {
  session_id: string;
  status: SessionStatus;
  progress: number;
  created_at: string; // ISO 8601 format
}

// 세션 목록
interface SessionList {
  sessions: SessionListItem[];
  total: number;
}
```

---

### 세션 생성 요청

```typescript
// 스타일 타입
type AudioStyle = "lecture" | "explain";

// 난이도 타입
type Difficulty = "basic" | "intermediate" | "advanced";

// 세션 생성 요청 (FormData)
interface CreateSessionRequest {
  files?: File[]; // 최대 4개
  links?: string; // JSON string array, 최대 4개
  main_kind: "file" | "link";
  main_index: number; // 0-based index
  voice_id?: string; // default: "Fenrir"
  style?: AudioStyle; // default: "explain"
  duration?: number; // default: 5 (분)
  difficulty?: Difficulty; // default: "intermediate"
  user_prompt?: string; // default: ""
}

// 세션 생성 응답
interface CreateSessionResponse {
  session_id: string;
  status: "processing";
  progress: number;
  current_step: string;
  created_at: string;
}
```

---

## API 클라이언트

### 기본 클라이언트 구현

```typescript
class AudiobookApiClient {
  private baseUrl: string;
  private token: string;

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  /**
   * 공통 HTTP 요청 메서드
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<ApiResponse<T>> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        "X-Internal-Service-Token": this.token,
        ...options.headers,
      },
    });

    return response.json();
  }

  /**
   * 채널 생성
   */
  async createChannel(): Promise<ApiResponse<Channel>> {
    return this.request<Channel>("/v1/channels", { method: "POST" });
  }

  /**
   * 채널 삭제
   */
  async deleteChannel(channelId: string): Promise<ApiResponse<null>> {
    return this.request<null>(`/v1/channels/${channelId}`, {
      method: "DELETE",
    });
  }

  /**
   * 세션 생성
   */
  async createSession(
    channelId: string,
    data: CreateSessionRequest,
  ): Promise<ApiResponse<CreateSessionResponse>> {
    const formData = new FormData();

    // 파일 추가
    if (data.files) {
      data.files.forEach((file) => formData.append("files", file));
    }

    // 링크 추가
    if (data.links) {
      formData.append("links", data.links);
    }

    // 필수 파라미터
    formData.append("main_kind", data.main_kind);
    formData.append("main_index", data.main_index.toString());

    // 선택 파라미터
    if (data.voice_id) formData.append("voice_id", data.voice_id);
    if (data.style) formData.append("style", data.style);
    if (data.duration) formData.append("duration", data.duration.toString());
    if (data.difficulty) formData.append("difficulty", data.difficulty);
    if (data.user_prompt) formData.append("user_prompt", data.user_prompt);

    return this.request<CreateSessionResponse>(
      `/v1/channels/${channelId}/sessions`,
      {
        method: "POST",
        body: formData,
      },
    );
  }

  /**
   * 세션 조회
   */
  async getSession(
    channelId: string,
    sessionId: string,
  ): Promise<ApiResponse<SessionDetail>> {
    return this.request<SessionDetail>(
      `/v1/channels/${channelId}/sessions/${sessionId}`,
    );
  }

  /**
   * 세션 목록 조회
   */
  async listSessions(
    channelId: string,
    limit = 50,
    offset = 0,
  ): Promise<ApiResponse<SessionList>> {
    return this.request<SessionList>(
      `/v1/channels/${channelId}/sessions?limit=${limit}&offset=${offset}`,
    );
  }

  /**
   * 세션 삭제
   */
  async deleteSession(
    channelId: string,
    sessionId: string,
  ): Promise<ApiResponse<null>> {
    return this.request<null>(
      `/v1/channels/${channelId}/sessions/${sessionId}`,
      { method: "DELETE" },
    );
  }

  /**
   * 오디오 스트리밍 URL 생성
   */
  getAudioUrl(channelId: string, sessionId: string, chapter = 1): string {
    return `${this.baseUrl}/v1/channels/${channelId}/files/audio/${sessionId}/${chapter}`;
  }
}
```

---

## 사용 예시

### 클라이언트 초기화

```typescript
// 환경별 Base URL 설정
const API_BASE_URL =
  process.env.NODE_ENV === "production"
    ? "https://gepeto-api-function-prod.azurewebsites.net"
    : "http://localhost:4001";

const API_TOKEN = process.env.INTERNAL_SERVICE_TOKEN || "your-token";

// 클라이언트 인스턴스 생성
const client = new AudiobookApiClient(API_BASE_URL, API_TOKEN);
```

---

### 채널 생성 및 세션 생성

```typescript
async function createAudiobook(pdfFile: File) {
  try {
    // 1. 채널 생성
    const channelResponse = await client.createChannel();

    if (!channelResponse.success) {
      console.error("채널 생성 실패:", channelResponse.message);
      return;
    }

    const channelId = channelResponse.data!.channel_id;
    console.log("채널 생성 성공:", channelId);

    // 2. 세션 생성
    const sessionResponse = await client.createSession(channelId, {
      files: [pdfFile],
      main_kind: "file",
      main_index: 0,
      duration: 10,
      style: "lecture",
      difficulty: "intermediate",
    });

    if (!sessionResponse.success) {
      console.error("세션 생성 실패:", sessionResponse.message);
      return;
    }

    const sessionId = sessionResponse.data!.session_id;
    console.log("세션 생성 성공:", sessionId);

    return { channelId, sessionId };
  } catch (error) {
    console.error("API 호출 오류:", error);
  }
}
```

---

### 세션 상태 확인

```typescript
async function checkSessionStatus(channelId: string, sessionId: string) {
  const response = await client.getSession(channelId, sessionId);

  if (!response.success) {
    console.error("세션 조회 실패:", response.message);
    return null;
  }

  const session = response.data!;

  console.log(`세션 상태: ${session.status}`);
  console.log(`진행률: ${session.progress}%`);
  console.log(`현재 단계: ${session.current_step}`);

  if (session.status === "completed") {
    console.log("완료! 총 길이:", session.result?.total_duration, "초");
  } else if (session.status === "failed") {
    console.error("실패:", session.error);
  }

  return session;
}
```

---

### 오디오 재생

```typescript
function playAudio(channelId: string, sessionId: string) {
  const audioUrl = client.getAudioUrl(channelId, sessionId);

  // HTML5 Audio 사용
  const audio = new Audio(audioUrl);
  audio.play();

  // 또는 <audio> 태그에 설정
  const audioElement = document.getElementById(
    "audio-player",
  ) as HTMLAudioElement;
  audioElement.src = audioUrl;
  audioElement.play();
}
```

---

## 폴링 패턴

세션 생성 후 완료 여부를 확인하려면 주기적으로 세션 상태를 조회해야 합니다.

### 기본 폴링 구현

```typescript
async function pollSessionStatus(
  client: AudiobookApiClient,
  channelId: string,
  sessionId: string,
  options?: {
    interval?: number; // 폴링 간격 (ms), 기본값: 3000
    onProgress?: (progress: number, step: string) => void;
    onComplete?: (result: SessionResult) => void;
    onError?: (error: string) => void;
  },
): Promise<void> {
  const interval = options?.interval || 3000;

  const poll = async () => {
    const response = await client.getSession(channelId, sessionId);

    if (!response.success) {
      options?.onError?.("세션 조회 실패");
      return;
    }

    const session = response.data!;

    switch (session.status) {
      case "processing":
        options?.onProgress?.(session.progress, session.current_step);
        setTimeout(poll, interval); // 3초 후 재시도
        break;

      case "completed":
        options?.onComplete?.(session.result!);
        break;

      case "failed":
        options?.onError?.(session.error || "알 수 없는 오류");
        break;
    }
  };

  poll();
}
```

## 변경 이력

### v1.0.0 (2025-02-03)

- 초기 TypeScript 가이드 작성
- 타입 정의 및 API 클라이언트 구현
- 폴링 패턴 가이드 추가

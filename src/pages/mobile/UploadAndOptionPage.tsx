// src/pages/mobile/UploadAndOptionsPage.tsx
/**
 * ============================================================
 * 팟캐스트 업로드 & 옵션 설정 페이지
 * ============================================================
 *
 * 핵심 개념:
 * 1. 프로젝트 자료실(projectInputs) - 서버에 이미 저장된 영구 데이터
 * 2. 신규 업로드 파일(uploadedFiles) - 이번에 추가할 파일들
 * 3. 주 소스(mainInputId) - 팟캐스트 생성의 중심이 되는 자료 1개 (필수)
 * 4. 보조 소스 - 주 소스 외 최대 3개까지 추가 가능
 *
 * 백엔드 요구사항:
 * - /outputs/generate에 main_input_id 필수 전달
 * - input_content_ids는 JSON string 형태
 * - 신규 파일은 먼저 /inputs/upload로 업로드 후 ID 획득
 */

import { useState, useRef, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  ChevronLeft,
  Upload,
  FileText,
  X,
  Edit3,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Link as LinkIcon,
} from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

// ============================================================
// 타입 정의
// ============================================================

/** 업로드할 파일 인터페이스 */
interface UploadedFile {
  id: string; // 프론트엔드에서 관리하는 임시 ID
  file?: File; // File 객체 (파일인 경우)
  url?: string; // URL 문자열 (링크인 경우)
  name: string; // 표시할 이름
  type: "pdf" | "docx" | "txt" | "pptx" | "url";
  size?: number; // 파일 크기 (bytes)
}

/** 기존 프로젝트 자료 인터페이스 */
interface ProjectInput {
  id: number; // 서버 DB의 input_contents.id
  title: string;
  created_at: string;
}

const UploadAndOptionsPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  // ============================================================
  // 라우터 state에서 전달받은 값들
  // ============================================================
  const selectedVoice = location.state?.selectedVoice || "";
  const selectedVoiceLabel =
    location.state?.selectedVoiceLabel || selectedVoice;
  const existingProjectId = location.state?.projectId;

  const userId = localStorage.getItem("user_id");

  // ============================================================
  // 상태 관리
  // ============================================================

  /** 프로젝트에 이미 업로드된 자료 목록 */
  const [projectInputs, setProjectInputs] = useState<ProjectInput[]>([]);

  /** 신규 업로드할 파일 목록 (아직 서버에 없음) */
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  /** 기존 자료 중 선택된 ID들 */
  const [selectedExistingIds, setSelectedExistingIds] = useState<number[]>([]);

  /**
   * 주 소스 ID (필수)
   * - 기존 자료를 선택한 경우: input ID (number)
   * - 신규 파일을 선택한 경우: 임시 ID (string)
   */
  const [mainSourceId, setMainSourceId] = useState<string | number | null>(
    null
  );

  /** 팟캐스트 옵션 */
  const [duration, setDuration] = useState<number>(5);
  const [voiceStyle, setVoiceStyle] = useState<"single" | "dialogue">("single");
  const [prompt, setPrompt] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  /** UI 상태 */
  const [showAddModal, setShowAddModal] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ============================================================
  // 프로젝트 기존 자료 불러오기
  // ============================================================
  useEffect(() => {
    if (!existingProjectId) {
      console.warn("⚠️ projectId가 전달되지 않았습니다.");
      return;
    }

    fetch(`${API_BASE_URL}/inputs/list?project_id=${existingProjectId}`)
      .then((res) => res.json())
      .then((json) => setProjectInputs(json.inputs ?? []))
      .catch((e) => console.error("기존 자료 불러오기 실패:", e));
  }, [existingProjectId]);

  // ============================================================
  // 유틸리티 함수들
  // ============================================================

  /** 파일 확장자로 타입 결정 */
  const getFileType = (
    filename: string
  ): "pdf" | "docx" | "txt" | "pptx" | "url" => {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return "pdf";
    if (ext === "docx" || ext === "doc") return "docx";
    if (ext === "txt") return "txt";
    if (ext === "pptx" || ext === "ppt") return "pptx";
    return "txt";
  };

  /** 파일 타입별 아이콘 */
  const getFileIcon = (type: string) => {
    const iconClass = "w-10 h-10";
    switch (type) {
      case "pdf":
        return <div className={`${iconClass} text-red-500 font-bold`}>PDF</div>;
      case "docx":
        return (
          <div className={`${iconClass} text-blue-500 font-bold`}>DOC</div>
        );
      case "txt":
        return (
          <div className={`${iconClass} text-gray-500 font-bold`}>TXT</div>
        );
      case "pptx":
        return (
          <div className={`${iconClass} text-orange-500 font-bold`}>PPT</div>
        );
      case "url":
        return <LinkIcon className={`${iconClass} text-green-500`} />;
      default:
        return <FileText className={iconClass} />;
    }
  };

  /** 파일 크기 포맷팅 */
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
  };

  /** 파일 유효성 검증 */
  const validateFiles = (fileList: File[]) => {
    const allowedExtensions = [".pdf", ".docx", ".txt", ".pptx"];
    const validFiles = fileList.filter((file) => {
      const extension = "." + file.name.split(".").pop()?.toLowerCase();
      return allowedExtensions.includes(extension);
    });

    if (validFiles.length !== fileList.length) {
      alert("PDF, DOCX, TXT, PPTX 파일만 업로드 가능합니다.");
    }

    // 최대 4개 제한
    const totalCount =
      uploadedFiles.length + validFiles.length + selectedExistingIds.length;
    if (totalCount > 4) {
      alert("최대 4개까지만 업로드 가능합니다.");
      return validFiles.slice(
        0,
        4 - uploadedFiles.length - selectedExistingIds.length
      );
    }

    return validFiles;
  };

  // ============================================================
  // 이벤트 핸들러들
  // ============================================================

  /** 파일 선택 핸들러 */
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    const validFiles = validateFiles(selected);
    if (validFiles.length === 0) return;

    const newFiles: UploadedFile[] = validFiles.map((file) => ({
      id: `file-${Date.now()}-${Math.random()}`, // 임시 ID
      file,
      name: file.name,
      type: getFileType(file.name),
      size: file.size,
    }));

    setUploadedFiles((prev) => [...prev, ...newFiles]);
    setShowAddModal(false);
    setIsDragging(false);
    setUrlInput("");
    e.target.value = ""; // 같은 파일 재선택 가능하도록
  };

  /** 드래그 오버 */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  /** 드롭 핸들러 */
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const dropped = Array.from(e.dataTransfer.files);
    const validFiles = validateFiles(dropped);
    if (validFiles.length === 0) return;

    const newFiles: UploadedFile[] = validFiles.map((file) => ({
      id: `file-${Date.now()}-${Math.random()}`,
      file,
      name: file.name,
      type: getFileType(file.name),
      size: file.size,
    }));

    setUploadedFiles((prev) => [...prev, ...newFiles]);
    setShowAddModal(false);
    setUrlInput("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  /** URL 추가 */
  const handleAddUrl = () => {
    if (!urlInput.trim()) {
      alert("URL을 입력해주세요.");
      return;
    }

    const totalCount = uploadedFiles.length + 1 + selectedExistingIds.length;
    if (totalCount > 4) {
      alert("최대 4개까지만 업로드 가능합니다.");
      return;
    }

    const newUrl: UploadedFile = {
      id: `url-${Date.now()}`,
      url: urlInput,
      name: urlInput,
      type: "url",
    };

    setUploadedFiles([...uploadedFiles, newUrl]);
    setUrlInput("");
    setShowAddModal(false);
  };

  /** 파일 삭제 */
  const removeFile = (id: string) => {
    setUploadedFiles(uploadedFiles.filter((f) => f.id !== id));
    if (mainSourceId === id) {
      setMainSourceId(null);
    }
  };

  /** 기존 자료 선택/해제 토글 */
  const toggleExistingInput = (inputId: number) => {
    if (selectedExistingIds.includes(inputId)) {
      // 선택 해제
      setSelectedExistingIds((prev) => prev.filter((id) => id !== inputId));

      // 주 소스로 선택되어 있었다면 해제
      if (mainSourceId === inputId) {
        setMainSourceId(null);
      }
    } else {
      // 선택
      const totalCount = uploadedFiles.length + selectedExistingIds.length + 1;
      if (totalCount > 4) {
        alert("최대 4개까지만 선택 가능합니다.");
        return;
      }
      setSelectedExistingIds((prev) => [...prev, inputId]);
    }
  };

  // ============================================================
  // 팟캐스트 생성 메인 로직
  // ============================================================
  const handleSubmit = async () => {
    // ============================
    // 1️⃣ 유효성 검증
    // ============================
    const totalSources = uploadedFiles.length + selectedExistingIds.length;

    if (totalSources === 0) {
      alert("최소 1개 이상의 자료를 업로드해주세요.");
      return;
    }

    if (!mainSourceId) {
      alert("주 소스를 하나 선택해주세요.");
      return;
    }

    if (!prompt.trim()) {
      alert("프롬프트를 입력해주세요.");
      return;
    }

    if (!selectedVoice) {
      alert("목소리 선택이 필요합니다.");
      navigate("/mobile/voice-selection");
      return;
    }

    setIsSubmitting(true);

    try {
      let projectId = existingProjectId;

      // ============================
      // 2️⃣ 프로젝트 생성 (없는 경우만)
      // ============================
      if (!projectId) {
        const projectRes = await fetch(`${API_BASE_URL}/projects/create`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            title: "새 팟캐스트",
          }),
        });

        const projectData = await projectRes.json();
        projectId = projectData.project.id;
      }

      // ============================
      // 3️⃣ 신규 파일 업로드
      // ============================
      let newInputIds: number[] = [];
      let uploadedMainInputId: number | null = null;

      if (uploadedFiles.length > 0) {
        const formData = new FormData();
        formData.append("user_id", userId!);
        formData.append("project_id", String(projectId));

        // URL 분리
        const urls = uploadedFiles
          .filter((f) => f.type === "url")
          .map((f) => f.url);
        formData.append("links", JSON.stringify(urls));

        // 파일 추가
        uploadedFiles
          .filter((f) => f.file)
          .forEach((f) => formData.append("files", f.file!));

        // 업로드 API 호출
        const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
          method: "POST",
          body: formData,
        });

        if (!uploadRes.ok) {
          throw new Error("파일 업로드 실패");
        }

        const uploadData = await uploadRes.json();
        newInputIds = uploadData.inputs.map((i: any) => i.id);

        // 🔑 주 소스가 신규 업로드 파일인 경우, 해당 input_id 찾기
        if (typeof mainSourceId === "string") {
          const mainFileIndex = uploadedFiles.findIndex(
            (f) => f.id === mainSourceId
          );
          if (mainFileIndex !== -1 && mainFileIndex < newInputIds.length) {
            uploadedMainInputId = newInputIds[mainFileIndex];
          }
        }
      }

      // ============================
      // 4️⃣ 모든 input_ids 합치기
      // ============================
      const allInputIds = [...selectedExistingIds, ...newInputIds];

      // ============================
      // 5️⃣ main_input_id 결정
      // ============================
      let finalMainInputId: number;

      if (typeof mainSourceId === "number") {
        // 기존 자료를 주 소스로 선택한 경우
        finalMainInputId = mainSourceId;
      } else if (uploadedMainInputId !== null) {
        // 신규 파일을 주 소스로 선택한 경우
        finalMainInputId = uploadedMainInputId;
      } else {
        alert("주 소스 설정에 실패했습니다.");
        setIsSubmitting(false);
        return;
      }

      // ============================
      // 6️⃣ 팟캐스트 생성 요청
      // ============================
      const generateForm = new FormData();
      generateForm.append("project_id", String(projectId));
      generateForm.append("input_content_ids", JSON.stringify(allInputIds));
      generateForm.append("main_input_id", String(finalMainInputId)); // ✅ 필수!
      generateForm.append("host1", selectedVoice);
      generateForm.append("host2", ""); // 현재 사용 안 함
      generateForm.append(
        "style",
        voiceStyle === "dialogue" ? "explain" : "lecture"
      );
      generateForm.append("duration", String(duration));
      generateForm.append("user_prompt", prompt.trim());

      const genRes = await fetch(`${API_BASE_URL}/outputs/generate`, {
        method: "POST",
        body: generateForm,
      });

      if (!genRes.ok) {
        throw new Error("팟캐스트 생성 요청 실패");
      }

      const { output_id } = await genRes.json();

      // ============================
      // 7️⃣ 생성 중 화면으로 이동
      // ============================
      navigate(`/mobile/generating/${output_id}`, {
        state: { projectId, outputId: output_id },
      });
    } catch (err) {
      console.error("생성 실패:", err);
      alert("팟캐스트 생성 중 오류가 발생했습니다.");
      setIsSubmitting(false);
    }
  };

  // ============================================================
  // 계산된 값들
  // ============================================================
  const totalCount = uploadedFiles.length + selectedExistingIds.length;
  const canAddMore = totalCount < 4;

  // ============================================================
  // UI 렌더링
  // ============================================================
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col relative">
      {/* ==================== Header ==================== */}
      <header className="bg-white border-b px-4 py-3 flex items-center sticky top-0 z-20">
        <button
          onClick={() => navigate(-1)}
          className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft className="w-6 h-6 text-gray-700" />
        </button>
        <h1 className="text-lg font-bold ml-2">팟캐스트 설정</h1>
      </header>

      {/* ==================== Content ==================== */}
      <div className="flex-1 overflow-y-auto p-4 pb-24">
        {/* 선택한 목소리 뱃지 */}
        <div className="bg-white border border-gray-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">선택한 목소리:</span>
            <span className="font-semibold text-gray-900">
              {selectedVoiceLabel}
            </span>
          </div>
          <button
            onClick={() => navigate("/mobile/voice-selection")}
            className="text-blue-600 text-sm font-medium"
          >
            변경하기
          </button>
        </div>

        {/* ==================== 기존 프로젝트 자료 ==================== */}
        {projectInputs.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
            <h3 className="font-bold text-gray-900 mb-3">기존 업로드 파일</h3>
            <p className="text-xs text-gray-600 mb-3">
              이미 프로젝트에 저장된 자료를 재사용할 수 있습니다.
            </p>
            <div className="space-y-2">
              {projectInputs.map((input) => {
                const isChecked = selectedExistingIds.includes(input.id);
                const isMain = mainSourceId === input.id;

                return (
                  <div
                    key={input.id}
                    className={`flex items-center gap-3 p-3 border rounded-lg transition-colors ${
                      isChecked
                        ? "border-blue-300 bg-blue-50"
                        : "border-gray-200"
                    }`}
                  >
                    {/* 체크박스 (선택/해제) */}
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleExistingInput(input.id)}
                      className="w-5 h-5 flex-shrink-0"
                    />

                    {/* 파일 아이콘 */}
                    <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />

                    {/* 파일 정보 */}
                    <span className="text-sm text-gray-900 flex-1 truncate">
                      {input.title}
                    </span>

                    {/* 주 소스 선택 라디오 (체크된 경우만 표시) */}
                    {isChecked && (
                      <div className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="mainSource"
                          checked={isMain}
                          onChange={() => setMainSourceId(input.id)}
                          className="w-5 h-5 flex-shrink-0"
                        />
                        {isMain && (
                          <span className="text-xs text-blue-600 font-semibold">
                            주 소스
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ==================== 수업 자료 업로드 ==================== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-gray-900 flex items-center gap-2">
              📁 수업 자료 업로드
            </h3>
            <button
              onClick={() => setShowAddModal(true)}
              disabled={!canAddMore}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Plus className="w-4 h-4" />
              자료 추가
            </button>
          </div>

          <p className="text-xs text-gray-500 mb-3">
            • 주 강의 자료는 <b>1개만</b> 선택할 수 있어요. 주 강의자료 중심으로
            내용이 생성됩니다. <br />• 이번 생성에 사용할 자료는{" "}
            <b>{totalCount}/4</b>개 선택됨
          </p>

          {uploadedFiles.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              자료를 추가해주세요
            </div>
          ) : (
            <div className="space-y-2">
              {uploadedFiles.map((file) => {
                const isMain = mainSourceId === file.id;

                return (
                  <div
                    key={file.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      isMain
                        ? "border-blue-400 bg-blue-50"
                        : "border-gray-200 bg-gray-50"
                    }`}
                  >
                    {/* 주 소스 선택 라디오 */}
                    <input
                      type="radio"
                      name="mainSource"
                      checked={isMain}
                      onChange={() => setMainSourceId(file.id)}
                      className="w-5 h-5 flex-shrink-0"
                    />

                    {/* 파일 아이콘 */}
                    <div className="flex-shrink-0">
                      {getFileIcon(file.type)}
                    </div>

                    {/* 파일 정보 */}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 text-sm truncate">
                        {file.name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatFileSize(file.size)}
                      </div>
                    </div>

                    {/* 주 소스 뱃지 */}
                    {isMain && (
                      <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded font-semibold">
                        주 소스
                      </span>
                    )}

                    {/* 삭제 버튼 */}
                    <button
                      onClick={() => removeFile(file.id)}
                      className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-5 h-5 text-red-500" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <p className="text-xs text-gray-500 mt-3">
            💡 지원 형식: PDF, DOCX, TXT, PPTX
          </p>
        </div>

        {/* ==================== 프롬프트 입력 (필수) ==================== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <label className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-1">
            <Edit3 className="w-4 h-4" />
            프롬프트 입력 <span className="text-red-500">*</span>
          </label>
          <p className="text-xs text-gray-600 mb-3">
            💡 프롬프트 내용이 참고 설정(길이·스타일)보다 우선 적용됩니다
          </p>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="예: 역사 자료에서 조선시대 부분으로만 만들어줘"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            rows={4}
          />
        </div>

        {/* ==================== 참고 설정 (선택) ==================== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between"
          >
            <h3 className="text-sm font-bold text-gray-900">
              참고 설정 (선택)
            </h3>
            {showAdvanced ? (
              <ChevronUp className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            )}
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-4">
              <p className="text-xs text-gray-500">
                기본값: 길이 5분, 강의형 스타일
              </p>

              {/* 팟캐스트 길이 */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-2 block">
                  팟캐스트 길이
                </label>
                <div className="flex gap-2">
                  {[5, 10, 15].map((min) => (
                    <button
                      key={min}
                      onClick={() => setDuration(min)}
                      className={`flex-1 py-2.5 rounded-lg border-2 font-medium transition-all ${
                        duration === min
                          ? "border-blue-600 bg-blue-50 text-blue-600"
                          : "border-gray-200 text-gray-700 hover:border-gray-300"
                      }`}
                    >
                      {min}분
                    </button>
                  ))}
                </div>
              </div>

              {/* 팟캐스트 스타일 */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-2 block">
                  팟캐스트 스타일
                </label>
                <div className="space-y-2">
                  <button
                    onClick={() => setVoiceStyle("single")}
                    className={`w-full py-3 px-4 rounded-lg border-2 text-left transition-all ${
                      voiceStyle === "single"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">
                        강의형 (선생님 단독)
                      </span>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          voiceStyle === "single"
                            ? "border-blue-600 bg-blue-600"
                            : "border-gray-300"
                        }`}
                      >
                        {voiceStyle === "single" && (
                          <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
                        )}
                      </div>
                    </div>
                  </button>

                  <button
                    onClick={() => setVoiceStyle("dialogue")}
                    className={`w-full py-3 px-4 rounded-lg border-2 text-left transition-all ${
                      voiceStyle === "dialogue"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">
                        대화형 (선생님-학생)
                      </span>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          voiceStyle === "dialogue"
                            ? "border-blue-600 bg-blue-600"
                            : "border-gray-300"
                        }`}
                      >
                        {voiceStyle === "dialogue" && (
                          <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
                        )}
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-gray-500 text-center mt-4">
          예상시간: 3~5분 소요
        </p>
      </div>

      {/* ==================== Bottom CTA ==================== */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 max-w-[430px] mx-auto">
        <button
          onClick={handleSubmit}
          disabled={
            isSubmitting || totalCount === 0 || !prompt.trim() || !mainSourceId
          }
          className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? "팟캐스트 생성 중..." : "팟캐스트 생성하기"}
        </button>
      </div>

      {/* ==================== 자료 추가 모달 ==================== */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-bold mb-4">파일 업로드</h3>

            {/* 파일 업로드 영역 */}
            <div
              className={`border-2 border-dashed rounded-xl p-6 text-center mb-4 transition-all ${
                isDragging
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-300 bg-gray-50"
              }`}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragLeave={() => setIsDragging(false)}
            >
              <Upload className="w-10 h-10 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600 mb-3">
                드래그 또는 클릭하여 파일 추가
              </p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                파일 선택
              </button>
              <p className="text-xs text-gray-500 mt-2">
                pdf, docx, txt, pptx 파일 지원
              </p>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.pptx"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            {/* URL 입력 */}
            <div className="mb-4">
              <label className="text-sm font-semibold text-gray-700 mb-2 block">
                링크로 추가하기
              </label>
              <input
                ref={urlInputRef}
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>

            {/* 버튼 */}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setUrlInput("");
                }}
                className="flex-1 py-3 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleAddUrl}
                disabled={!urlInput.trim()}
                className="flex-1 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                추가하기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadAndOptionsPage;

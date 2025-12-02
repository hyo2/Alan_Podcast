import { useState, useRef } from "react";
import { Upload, FileText, MoreVertical, Star } from "lucide-react";
import { API_BASE_URL } from "../lib/api";
import { useNavigate } from "react-router-dom";

const PODCAST_STYLES = [
  { id: "explain", label: "설명형" },
  { id: "debate", label: "토론형" },
  { id: "interview", label: "인터뷰" },
  { id: "summary", label: "요약 중심" },
];

const DocumentsPage = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<string[]>([]); // 빈 배열로 초기화
  const [hosts, setHosts] = useState({
    host1: "",
    host2: "",
  });
  const [selectedStyle, setSelectedStyle] = useState("");

  // 임시 호스트 목록 — 실제로는 API 요청으로 받아올 예정
  const hostList = [
    { id: "alan_male", name: "James" },
    { id: "alan_female", name: "Jenny" },
    { id: "calm_male", name: "차분한 남성" },
    { id: "energetic_female", name: "발랄한 여성" },
  ];

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles([...files, ...Array.from(e.target.files)]);
  };

  const addLinkField = () => {
    setLinks([...links, ""]);
  };

  const updateLink = (index: number, value: string) => {
    const updated = [...links];
    updated[index] = value;
    setLinks(updated);
  };

  // 제출 처리
  const handleSubmit = async () => {
    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        alert("로그인이 필요합니다.");
        return;
      }

      // 1) 새 프로젝트 생성
      const createRes = await fetch(`${API_BASE_URL}/projects/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          title: "새 팟캐스트 프로젝트",
          description: "",
        }),
      });

      const createData = await createRes.json();
      const projectId = createData.project.id;

      // ---------------------------
      // 2) FormData 구성
      // ---------------------------
      const formData = new FormData();

      formData.append("user_id", userId);
      formData.append("project_id", projectId);
      formData.append("host1", hosts.host1);
      formData.append("host2", hosts.host2);
      formData.append("style", selectedStyle);

      // 빈 링크 제거
      const filteredLinks = links.filter((l) => l.trim() !== "");
      formData.append("links", JSON.stringify(filteredLinks));

      // 파일 추가
      if (files.length > 0) {
        files.forEach((file) => {
          formData.append("files", file);
        });
      }

      // ---------------------------
      // 3) 업로드 API 호출
      // ---------------------------
      const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        alert("업로드 실패. 프로젝트를 삭제합니다.");

        // ⚠ 실패 시 프로젝트 삭제 API 호출
        await fetch(`${API_BASE_URL}/projects/${projectId}`, {
          method: "DELETE",
        });

        return;
      }

      const uploadData = await uploadRes.json();
      console.log("업로드 결과:", uploadData);

      // 성공 → 프로젝트 상세 화면 이동
      navigate(`/project/${projectId}`);
    } catch (err) {
      console.error("업로드 실패:", err);
      alert("업로드 중 오류가 발생했습니다.");
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">내 문서</h1>
        <p className="text-gray-600">
          문서를 업로드하고 Alan과 함께 분석해보세요
        </p>
      </div>

      {/* Upload Box */}
      <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-12 text-center hover:border-gray-400 hover:bg-gray-50 transition-all">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-xl flex items-center justify-center">
            <Upload className="w-8 h-8 text-gray-600" />
          </div>

          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            문서를 업로드하세요
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            PDF, DOCX, TXT 파일을 여러 개 업로드할 수 있습니다
          </p>

          {/* Only the button triggers file input */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors"
          >
            파일 선택
          </button>

          <input
            type="file"
            multiple
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Uploaded file list */}
          {files.length > 0 && (
            <div className="mt-6 text-left">
              <p className="font-semibold mb-2">선택된 파일:</p>
              <ul className="text-sm text-gray-700 ml-1">
                {files.map((file, idx) => (
                  <li
                    key={idx}
                    className="flex justify-between items-center py-1"
                  >
                    <span className="truncate max-w-xs">{file.name}</span>

                    {/* ❌ 삭제 버튼 */}
                    <button
                      onClick={() => {
                        const updated = files.filter((_, i) => i !== idx);
                        setFiles(updated);
                      }}
                      className="text-gray-400 hover:text-red-500 transition ml-3"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Options Panel */}
      <div className="mt-8 bg-white rounded-xl border border-gray-200 p-8">
        {/* 링크 입력 */}
        <div className="mb-8">
          <label className="font-semibold text-gray-800 block mb-3">
            링크로 문서 가져오기
          </label>

          {/* Links section */}
          <div className="flex flex-col gap-3">
            {links.map((link, idx) => (
              <div key={idx} className="flex gap-2 items-center">
                <input
                  type="text"
                  placeholder="https://example.com/article"
                  value={link}
                  onChange={(e) => updateLink(idx, e.target.value)}
                  className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />

                {/* 삭제 버튼 */}
                <button
                  onClick={() => {
                    const updated = links.filter((_, i) => i !== idx);
                    setLinks(updated);
                  }}
                  className="text-gray-400 hover:text-red-500 transition"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={addLinkField}
            className="mt-3 text-blue-600 font-semibold hover:underline"
          >
            + 링크 추가
          </button>
        </div>

        {/* 호스트 선택 */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            팟캐스트 호스트 선택
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Host 1 */}
            <div>
              <p className="text-gray-700 mb-2">호스트 1</p>
              <select
                value={hosts.host1}
                onChange={(e) => setHosts({ ...hosts, host1: e.target.value })}
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">선택하세요</option>
                {hostList.map((h) => (
                  <option value={h.id} key={h.id}>
                    {h.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Host 2 */}
            <div>
              <p className="text-gray-700 mb-2">호스트 2</p>
              <select
                value={hosts.host2}
                onChange={(e) => setHosts({ ...hosts, host2: e.target.value })}
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">선택하세요</option>
                {hostList.map((h) => (
                  <option value={h.id} key={h.id}>
                    {h.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 팟캐스트 스타일 선택 */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            팟캐스트 스타일 선택
          </h3>

          <div className="flex flex-wrap gap-3">
            {PODCAST_STYLES.map((style) => (
              <button
                key={style.id}
                onClick={() => setSelectedStyle(style.id)}
                className={`px-4 py-2 rounded-lg border ${
                  selectedStyle === style.id
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-gray-300 text-gray-700 hover:bg-gray-100"
                }`}
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          className="mt-6 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
        >
          팟캐스트 생성하기
        </button>
      </div>

      {/* Recent Documents */}
      <div className="mt-12">
        <h2 className="text-xl font-bold text-gray-900 mb-6">최근 문서</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Document Card */}
          <div className="bg-white rounded-xl p-6 border border-gray-200 hover:shadow-lg hover:border-gray-300 transition-all cursor-pointer">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-gray-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">
                    AI 연구 논문
                  </h3>
                  <p className="text-xs text-gray-500">2시간 전</p>
                </div>
              </div>
              <button className="p-1 hover:bg-gray-100 rounded">
                <MoreVertical className="w-4 h-4 text-gray-400" />
              </button>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2 mb-4">
              대규모 언어 모델의 최신 발전 동향과 실무 적용 사례를 다룬 연구
              논문입니다...
            </p>
            <div className="flex gap-2">
              <span className="px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">
                PDF
              </span>
              <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">
                요약 완료
              </span>
            </div>
          </div>

          {/* More cards... */}
          <div className="bg-white rounded-xl p-6 border border-gray-200 hover:shadow-lg hover:border-gray-300 transition-all cursor-pointer">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-gray-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">
                    마케팅 전략 보고서
                  </h3>
                  <p className="text-xs text-gray-500">1일 전</p>
                </div>
              </div>
              <button className="p-1 hover:bg-gray-100 rounded">
                <Star className="w-4 h-4 text-yellow-500" fill="currentColor" />
              </button>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2 mb-4">
              2025년 디지털 마케팅 트렌드 분석 및 전략 수립 가이드...
            </p>
            <div className="flex gap-2">
              <span className="px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">
                DOCX
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentsPage;

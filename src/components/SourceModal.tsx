import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useState, useRef } from "react";
import { Upload } from "lucide-react";
import type { ExistingSource, OutputContent } from "../types.ts";
import { API_BASE_URL } from "../lib/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  existingSources: ExistingSource[];
  projectId: string;
  onGenerated: (output: OutputContent) => void;
  onDelete: (id: number) => void;
}

export default function SourceModal({
  isOpen,
  onClose,
  existingSources,
  projectId,
  onGenerated,
  onDelete,
}: Props) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [links, setLinks] = useState<string[]>([]);
  const [host1, setHost1] = useState("");
  const [host2, setHost2] = useState("");
  const [style, setStyle] = useState("");
  const [title, setTitle] = useState("새 팟캐스트"); // placeholder로 수정하기
  const [isLoading, setIsLoading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  const userId = localStorage.getItem("user_id") || "";

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const addLinkField = () => setLinks((prev) => [...prev, ""]);
  const updateLink = (i: number, value: string) => {
    setLinks((prev) => prev.map((v, idx) => (idx === i ? value : v)));
  };
  const removeLink = (i: number) => {
    setLinks((prev) => prev.filter((_, idx) => idx !== i));
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles([...files, ...Array.from(e.target.files)]);
  };

  // 기존 소스 삭제 처리
  const handleDeleteExistingSource = async (sourceId: number) => {
    if (!window.confirm("정말 삭제하시겠습니까?")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/inputs/${sourceId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        alert("삭제 실패");
        return;
      }

      // 부모(ProjectDetailPage)의 상태도 업데이트
      onDelete(sourceId);

      // 선택 중이었다면 체크박스에서도 제거
      setSelectedIds((prev) => prev.filter((id) => id !== sourceId));
    } catch (err) {
      console.error("삭제 실패:", err);
    }
  };

  // 팟캐스트 생성 처리
  const handleGenerate = async () => {
    if (!userId) {
      alert("로그인이 필요합니다.");
      return;
    }
    if (!host1 || !host2) {
      alert("호스트를 선택해주세요.");
      return;
    }
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append("user_id", userId);
      formData.append("input_ids", JSON.stringify(selectedIds));
      formData.append(
        "links",
        JSON.stringify(links.filter((l) => l.trim() !== ""))
      );
      formData.append("host1", host1);
      formData.append("host2", host2);
      formData.append("style", style);
      formData.append("title", title);

      files.forEach((f) => formData.append("files", f));

      const res = await fetch(
        `${API_BASE_URL}/outputs/generate?project_id=${projectId}`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        console.error(await res.text());
        alert("팟캐스트 생성 실패");
        return;
      }

      const data = await res.json();
      onGenerated(data.output);
      onClose();
    } catch (err) {
      console.error(err);
      alert("오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const hostList = [
    { id: "alan_male", name: "James" },
    { id: "alan_female", name: "Jenny" },
    { id: "calm_male", name: "차분한 남성" },
    { id: "energetic_female", name: "발랄한 여성" },
  ];

  const PODCAST_STYLES = [
    { id: "explain", label: "설명형" },
    { id: "debate", label: "토론형" },
    { id: "interview", label: "인터뷰" },
    { id: "summary", label: "요약 중심" },
  ];

  return (
    <Transition show={isOpen} appear as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* 배경 */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40" />
        </Transition.Child>

        {/* 모달 내용 */}
        <div className="fixed inset-0 flex items-center justify-center p-6">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0 scale-95"
            enterTo="opacity-100 scale-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100 scale-100"
            leaveTo="opacity-0 scale-95"
          >
            <Dialog.Panel className="w-[780px] max-h-[90vh] overflow-y-auto bg-white rounded-xl shadow-xl p-6">
              {/* 헤더 */}
              <div className="flex justify-between items-center mb-4">
                <Dialog.Title className="text-xl font-semibold">
                  소스 선택
                </Dialog.Title>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 text-xl"
                >
                  ✕
                </button>
              </div>

              {/* 1. 기존 소스 목록 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">현재 프로젝트의 소스</h3>
                {existingSources.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    등록된 소스가 없습니다.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {existingSources.map((src) => (
                      <label
                        key={src.id}
                        className="flex items-center gap-3 p-2 border rounded-lg cursor-pointer hover:bg-gray-50"
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(src.id)}
                          onChange={() => toggleSelect(src.id)}
                        />
                        <span className="flex-1 truncate">{src.title}</span>
                        {/* 소스 삭제 버튼 */}
                        <button
                          onClick={() => handleDeleteExistingSource(src.id)}
                          className="text-red-500 hover:text-red-600 text-sm"
                        >
                          삭제
                        </button>
                      </label>
                    ))}
                  </div>
                )}
              </section>

              <hr className="my-4" />

              {/* 2. 새 파일 업로드 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">새 문서 업로드</h3>
                <div className="border-2 border-dashed rounded-lg p-4 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                      <Upload className="w-6 h-6 text-gray-500" />
                    </div>
                    <p className="text-sm text-gray-600">
                      PDF, DOCX, TXT 파일 업로드
                    </p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
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
                  </div>

                  {files.length > 0 && (
                    <ul className="mt-3 text-left text-sm text-gray-700">
                      {files.map((f, i) => (
                        <li key={i} className="flex justify-between">
                          <span className="truncate max-w-xs">{f.name}</span>
                          <button
                            className="text-gray-400 hover:text-red-500"
                            onClick={() =>
                              setFiles(files.filter((_, idx) => idx !== i))
                            }
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              {/* 3. 새 링크 추가 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">링크로 문서 추가</h3>
                {links.map((link, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={link}
                      onChange={(e) => updateLink(i, e.target.value)}
                      placeholder="https://example.com/article"
                      className="flex-1 px-3 py-2 border rounded"
                    />
                    <button
                      onClick={() => removeLink(i)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  onClick={addLinkField}
                  className="text-sm text-blue-600 font-semibold"
                >
                  + 링크 추가
                </button>
              </section>

              {/* 4. 호스트 / 스타일 선택 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-3">호스트 & 스타일</h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <p className="text-sm mb-1">호스트 1</p>
                    <select
                      value={host1}
                      onChange={(e) => setHost1(e.target.value)}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">선택하세요</option>
                      {hostList.map((h) => (
                        <option key={h.id} value={h.id}>
                          {h.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <p className="text-sm mb-1">호스트 2</p>
                    <select
                      value={host2}
                      onChange={(e) => setHost2(e.target.value)}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">선택하세요</option>
                      {hostList.map((h) => (
                        <option key={h.id} value={h.id}>
                          {h.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mb-4">
                  <p className="text-sm mb-2">팟캐스트 스타일</p>
                  <div className="flex flex-wrap gap-2">
                    {PODCAST_STYLES.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => setStyle(s.id)}
                        className={`px-3 py-1 rounded border text-sm ${
                          style === s.id
                            ? "bg-blue-600 text-white border-blue-600"
                            : "border-gray-300 text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-sm mb-1">팟캐스트 제목</p>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full px-3 py-2 border rounded"
                  />
                </div>
              </section>

              {/* 5. 하단 버튼 */}
              <div className="flex justify-center gap-3 mt-4">
                <button
                  onClick={handleGenerate}
                  className="px-5 py-2 rounded bg-blue-600 text-white font-semibold disabled:opacity-60"
                  disabled={isLoading}
                >
                  {isLoading ? "생성 중..." : "팟캐스트 생성하기"}
                </button>

                {/* 취소 버튼 */}
                {/* <button
                  onClick={onClose}
                  className="px-4 py-2 rounded border border-gray-300 text-gray-700"
                  disabled={isLoading}
                >
                  취소
                </button> */}
              </div>
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition>
  );
}

import { useState, useRef } from "react";
import { Upload } from "lucide-react";

interface Host {
  id: string;
  name: string;
}

interface Props {
  onSubmit: (data: {
    files: File[];
    links: string[];
    hosts: { host1: string; host2: string };
    style: string;
  }) => void;
}

const PODCAST_STYLES = [
  { id: "explain", label: "설명형" },
  { id: "debate", label: "토론형" },
  { id: "interview", label: "인터뷰" },
  { id: "summary", label: "요약 중심" },
];

export default function SourceInputForm({ onSubmit }: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<string[]>([]);
  const [hosts, setHosts] = useState({ host1: "", host2: "" });
  const [selectedStyle, setSelectedStyle] = useState("");

  const hostList: Host[] = [
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

  const handleSubmit = () => {
    onSubmit({
      files,
      links: links.filter((l) => l.trim() !== ""),
      hosts,
      style: selectedStyle,
    });
  };

  return (
    <div className="w-full">
      {/* Upload Box */}
      <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-8 text-center">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-xl flex items-center justify-center">
            <Upload className="w-8 h-8 text-gray-600" />
          </div>

          <h3 className="text-lg font-semibold mb-2">문서를 업로드하세요</h3>
          <p className="text-sm text-gray-600 mb-4">
            PDF, DOCX, TXT 파일을 여러 개 업로드할 수 있습니다
          </p>

          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
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

          {files.length > 0 && (
            <div className="mt-6 text-left">
              <p className="font-semibold mb-2">선택된 파일:</p>
              <ul className="text-sm text-gray-700 ml-1">
                {files.map((file, idx) => (
                  <li key={idx} className="flex justify-between py-1">
                    <span className="truncate max-w-xs">{file.name}</span>

                    <button
                      onClick={() =>
                        setFiles(files.filter((_, i) => i !== idx))
                      }
                      className="text-gray-400 hover:text-red-500"
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

      {/* Links */}
      <div className="mt-8">
        <label className="font-semibold block mb-3">링크로 문서 가져오기</label>

        {links.map((link, idx) => (
          <div key={idx} className="flex gap-2 items-center mb-2">
            <input
              type="text"
              value={link}
              onChange={(e) => updateLink(idx, e.target.value)}
              className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="https://example.com/article"
            />

            <button
              onClick={() => setLinks(links.filter((_, i) => i !== idx))}
              className="text-gray-400 hover:text-red-500"
            >
              ✕
            </button>
          </div>
        ))}

        <button
          onClick={addLinkField}
          className="mt-2 text-blue-600 font-semibold hover:underline"
        >
          + 링크 추가
        </button>
      </div>

      {/* Hosts */}
      <div className="mt-8">
        <h3 className="font-semibold mb-3">팟캐스트 호스트 선택</h3>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="text-gray-700 mb-2">호스트 1</p>
            <select
              value={hosts.host1}
              onChange={(e) => setHosts({ ...hosts, host1: e.target.value })}
              className="w-full px-4 py-3 border rounded-lg"
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
            <p className="text-gray-700 mb-2">호스트 2</p>
            <select
              value={hosts.host2}
              onChange={(e) => setHosts({ ...hosts, host2: e.target.value })}
              className="w-full px-4 py-3 border rounded-lg"
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
      </div>

      {/* Podcast style */}
      <div className="mt-8">
        <h3 className="font-semibold mb-3">팟캐스트 스타일 선택</h3>

        <div className="flex flex-wrap gap-3">
          {PODCAST_STYLES.map((style) => (
            <button
              key={style.id}
              onClick={() => setSelectedStyle(style.id)}
              className={`px-4 py-2 rounded-lg border ${
                selectedStyle === style.id
                  ? "bg-blue-600 text-white"
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
        className="mt-8 w-full px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold"
      >
        팟캐스트 생성하기
      </button>
    </div>
  );
}

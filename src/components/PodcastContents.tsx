import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../lib/api";

interface ImageItem {
  img_index: number;
  img_path: string;
  img_description: string;
  start_time: number | string;
  end_time: number | string;
}

interface ParsedLine {
  time: number;
  timeStr: string;
  text: string;
}

export default function PodcastContents({ outputId }: { outputId: number }) {
  const [data, setData] = useState<any>(null);
  const [parsedScript, setParsedScript] = useState<ParsedLine[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentImage, setCurrentImage] = useState<ImageItem | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  /** GET detail */
  useEffect(() => {
    axios.get(`${API_BASE_URL}/outputs/${outputId}`).then((res) => {
      setData(res.data);

      const parsed = parseScript(res.data.output.script_text);
      setParsedScript(parsed);

      if (res.data.images.length > 0) {
        setCurrentImage(res.data.images[0]);
      }
    });
  }, [outputId]);

  /** Sync audio position using real-time timeupdate event */
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handler = () => {
      const t = audio.currentTime;
      setCurrentTime(t);
      updateCurrentImage(t);
    };

    audio.addEventListener("timeupdate", handler);
    return () => audio.removeEventListener("timeupdate", handler);
  }, [data]);

  const updateCurrentImage = (t: number) => {
    if (!data?.images) return;

    const img = data.images.find((i: ImageItem) => {
      const start = parseFloat(i.start_time as any);
      const end = parseFloat(i.end_time as any);
      return t >= start && t <= end;
    });

    if (img) setCurrentImage(img);
  };

  const jumpToTime = (sec: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play();
    }
  };

  if (!data) return <div className="p-4">로딩 중...</div>;

  const { output, images } = data;

  return (
    <div className="bg-white shadow rounded-lg p-6 h-[800px] flex flex-col">
      {/* TOP FIXED AREA */}
      <div className="mb-4">
        <h1 className="text-xl font-bold">{output.title}</h1>
        <p className="text-gray-600 mt-1">{output.summary}</p>

        <audio ref={audioRef} controls className="w-full mt-3">
          <source src={output.storage_path} type="audio/mpeg" />
        </audio>
      </div>

      {/* BODY AREA (LEFT image / RIGHT script) */}
      <div className="flex flex-1 gap-6 overflow-hidden">
        {/* LEFT IMAGE SECTION */}
        <div className="w-1/2 flex flex-col">
          <div className="flex-1 bg-gray-100 rounded-lg flex items-center justify-center">
            {currentImage ? (
              <img
                src={currentImage.img_path}
                className="max-h-full max-w-full object-contain rounded"
              />
            ) : (
              <div>이미지 없음</div>
            )}
          </div>

          {/* Thumbnail list */}
          <div className="h-28 mt-4 overflow-x-auto flex gap-2">
            {images.map((img: ImageItem) => (
              <img
                key={img.img_index}
                src={img.img_path}
                className={`h-full rounded cursor-pointer ${
                  currentImage?.img_index === img.img_index
                    ? "ring-4 ring-blue-500"
                    : ""
                }`}
                onClick={() => jumpToTime(parseFloat(img.start_time as any))}
              />
            ))}
          </div>
        </div>

        {/* RIGHT SCRIPT SECTION */}
        <div className="w-1/2 border-l pl-4 overflow-y-auto">
          <h2 className="font-semibold mb-2">스크립트</h2>

          {parsedScript.map((line, idx) => (
            <div
              key={idx}
              className={`p-2 rounded cursor-pointer ${
                isCurrentLine(idx, parsedScript, currentTime)
                  ? "bg-blue-100"
                  : ""
              }`}
              onClick={() => jumpToTime(line.time)}
            >
              <span className="text-xs text-gray-400">{line.timeStr}</span>
              <span className="ml-2">{line.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** PARSE SCRIPT LINE */
function parseScript(script: string): ParsedLine[] {
  const lines = script.split("\n");

  return lines
    .map((l) => {
      const m = l.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$/);
      if (!m) return null;

      const timeStr = m[1];
      const text = m[2];

      const [hh, mm, ss] = timeStr.split(":").map(Number);
      const sec = hh * 3600 + mm * 60 + ss;

      return { time: sec, timeStr, text };
    })
    .filter(Boolean) as ParsedLine[];
}

/** HIGHLIGHT LOGIC (Until next line begins) */
function isCurrentLine(idx: number, parsed: ParsedLine[], t: number) {
  const start = parsed[idx].time;
  const next = parsed[idx + 1]?.time ?? Infinity;
  return t >= start && t < next;
}

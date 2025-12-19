// src/pages/mobile/GeneratingPage.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { Loader2, Check, FileText, Mic, Music } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface GeneratingStep {
  id: string;
  label: string;
  icon: React.ReactNode;
  status: "pending" | "processing" | "completed";
}

const GeneratingPage = () => {
  const navigate = useNavigate();
  const { outputId } = useParams<{ outputId: string }>();
  const location = useLocation();
  const projectId = location.state?.projectId;

  const [progress, setProgress] = useState(0);
  const [steps, setSteps] = useState<GeneratingStep[]>([
    {
      id: "analyze",
      label: "자료 분석 완료",
      icon: <FileText className="w-5 h-5" />,
      status: "pending",
    },
    {
      id: "script",
      label: "스크립트 생성 완료",
      icon: <Mic className="w-5 h-5" />,
      status: "pending",
    },
    {
      id: "audio",
      label: "음성 합성 중...",
      icon: <Music className="w-5 h-5" />,
      status: "pending",
    },
    {
      id: "final",
      label: "최종 파일 생성",
      icon: <Check className="w-5 h-5" />,
      status: "pending",
    },
  ]);

  useEffect(() => {
    if (!outputId) return;

    // 진행 단계 시뮬레이션
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 95) return prev;
        return prev + Math.random() * 5;
      });
    }, 500);

    // 단계별 진행 시뮬레이션
    const stepTimers = [
      setTimeout(() => updateStep("analyze", "completed"), 1000),
      setTimeout(() => updateStep("script", "completed"), 3000),
      setTimeout(() => updateStep("audio", "processing"), 3500),
      setTimeout(() => updateStep("final", "processing"), 6000),
    ];

    // 상태 폴링
    const pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/outputs/${outputId}/status`);

        if (res.status === 404) {
          console.log("Output not found yet");
          return;
        }

        if (!res.ok) return;

        const data = await res.json();

        if (data.status === "completed") {
          clearInterval(pollingInterval);
          clearInterval(progressInterval);
          stepTimers.forEach(clearTimeout);
          setProgress(100);

          // 완료 화면으로 이동
          setTimeout(() => {
            navigate(`/mobile/completed/${outputId}`, {
              state: { projectId },
            });
          }, 1000);
        } else if (data.status === "failed") {
          clearInterval(pollingInterval);
          clearInterval(progressInterval);
          alert("팟캐스트 생성에 실패했습니다.");
          navigate("/mobile");
        }
      } catch (err) {
        console.error("Status check error:", err);
      }
    }, 3000);

    return () => {
      clearInterval(progressInterval);
      clearInterval(pollingInterval);
      stepTimers.forEach(clearTimeout);
    };
  }, [outputId]);

  const updateStep = (
    stepId: string,
    status: "pending" | "processing" | "completed"
  ) => {
    setSteps((prev) =>
      prev.map((step) => (step.id === stepId ? { ...step, status } : step))
    );
  };

  const handleCancel = () => {
    if (
      !confirm(
        "팟캐스트 생성을 취소하시겠습니까? 지금까지의 작업이 삭제됩니다."
      )
    ) {
      return;
    }

    // 취소 처리 (필요시 DELETE API 호출)
    navigate("/mobile");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex flex-col items-center justify-center p-4">
      {/* Main Content */}
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <Music className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            팟캐스트 생성 중 ...
          </h1>
          <p className="text-gray-600 text-sm">
            잠시만 기다려주세요. 곧 완성됩니다!
          </p>
        </div>

        {/* Progress Bar */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-700">진행률</span>
            <span className="text-2xl font-bold text-blue-600">
              {Math.round(progress)}%
            </span>
          </div>

          <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Steps */}
          <div className="mt-6 space-y-3">
            {steps.map((step) => (
              <div
                key={step.id}
                className="flex items-center gap-3 p-3 rounded-lg transition-all"
                style={{
                  backgroundColor:
                    step.status === "completed"
                      ? "#f0fdf4"
                      : step.status === "processing"
                      ? "#eff6ff"
                      : "#f9fafb",
                }}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                    step.status === "completed"
                      ? "bg-green-500 text-white"
                      : step.status === "processing"
                      ? "bg-blue-500 text-white animate-pulse"
                      : "bg-gray-300 text-gray-500"
                  }`}
                >
                  {step.status === "completed" ? (
                    <Check className="w-4 h-4" />
                  ) : step.status === "processing" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    step.icon
                  )}
                </div>

                <span
                  className={`text-sm font-medium ${
                    step.status === "completed"
                      ? "text-green-700"
                      : step.status === "processing"
                      ? "text-blue-700"
                      : "text-gray-500"
                  }`}
                >
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Cancel Button */}
        <button
          onClick={handleCancel}
          className="w-full py-3 bg-white text-red-600 border-2 border-red-600 rounded-xl font-semibold hover:bg-red-50 transition-colors"
        >
          취소 하기
        </button>
      </div>
    </div>
  );
};

export default GeneratingPage;

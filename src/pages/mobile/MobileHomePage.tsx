import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface Project {
  id: number;
  title: string;
  created_at: string;
}

const MobileHomePage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const userId = localStorage.getItem("user_id");

  const [visibleCount, setVisibleCount] = useState(6);

  useEffect(() => {
    if (!userId) {
      navigate("/mobile/auth");
      return;
    }
    fetchProjects();
  }, [userId]);

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/projects?user_id=${userId}`);
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      console.error("프로젝트 불러오기 실패:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      {/* Welcome */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-1">환영합니다!</h2>
        <p className="text-gray-600 text-sm">새로운 팟캐스트를 만들어보세요</p>
      </div>

      {/* Create */}
      <button
        onClick={() => navigate("/mobile/voice-selection")}
        className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg mb-6 hover:bg-blue-700 transition shadow-lg"
      >
        팟캐스트 만들기
      </button>

      {/* Projects */}
      <div className="bg-white rounded-2xl border p-4">
        <h3 className="text-lg font-bold mb-4">프로젝트 목록</h3>

        <div
          className="flex-1 overflow-y-auto space-y-3 max-h-[45vh]"
          onScroll={(e) => {
            const el = e.currentTarget;

            // 스크롤이 거의 바닥에 닿았을 때
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20) {
              setVisibleCount((prev) => Math.min(prev + 10, projects.length));
            }
          }}
        >
          {projects.slice(0, visibleCount).map((project) => (
            <button
              key={project.id}
              onClick={() => navigate(`/mobile/project/${project.id}`)}
              className="w-full bg-gray-50 border rounded-xl p-4 flex items-center justify-between"
            >
              <div className="text-left">
                <h4 className="font-semibold">{project.title}</h4>
                <p className="text-xs text-gray-500">
                  {new Date(project.created_at).toLocaleDateString("ko-KR")}
                </p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </button>
          ))}

          {/* 하단 로딩 힌트 (선택) */}
          {visibleCount < projects.length && (
            <div className="text-center text-xs text-gray-400 py-2">
              더 불러오는 중…
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MobileHomePage;

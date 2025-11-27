// src/pages/DocumentsPage.tsx
import { Upload, FileText, MoreVertical, Star } from 'lucide-react';

const DocumentsPage = () => {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">내 문서</h1>
        <p className="text-gray-600">문서를 업로드하고 Alan과 함께 분석해보세요</p>
      </div>
      
      {/* Upload Section */}
      <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-12 text-center hover:border-gray-400 hover:bg-gray-50 transition-all cursor-pointer">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-xl flex items-center justify-center">
            <Upload className="w-8 h-8 text-gray-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            문서를 업로드하세요
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            PDF, DOCX, TXT 파일을 드래그하거나 클릭하여 업로드
          </p>
          <button className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors">
            파일 선택
          </button>
        </div>
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
                  <h3 className="font-semibold text-gray-900 truncate">AI 연구 논문</h3>
                  <p className="text-xs text-gray-500">2시간 전</p>
                </div>
              </div>
              <button className="p-1 hover:bg-gray-100 rounded">
                <MoreVertical className="w-4 h-4 text-gray-400" />
              </button>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2 mb-4">
              대규모 언어 모델의 최신 발전 동향과 실무 적용 사례를 다룬 연구 논문입니다...
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
                  <h3 className="font-semibold text-gray-900 truncate">마케팅 전략 보고서</h3>
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
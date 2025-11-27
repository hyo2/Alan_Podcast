// src/components/Sidebar.tsx
import { 
  FileText, Clock, Star, Trash2, 
  Plus, Search, Pencil, Sparkles, BarChart 
} from 'lucide-react';
import AlanIcon from './AlanIcon';

const Sidebar = () => {
  return (
    <aside className="fixed left-0 top-0 h-full w-16 bg-white border-r border-gray-200 flex flex-col items-center py-6 space-y-6 z-50">
      {/* Logo - A만 */}
      <button className="w-10 h-10 flex items-center justify-center" aria-label="Alan 홈">
        <AlanIcon width={15} height={20} className="text-gray-900" />
      </button>

      {/* 메뉴 아이콘들 */}
      <nav className="flex-1 flex flex-col items-center space-y-4">
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
          title="새 문서"
        >
          <Plus className="w-5 h-5 text-gray-600" />
        </button>
        
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
          title="검색"
        >
          <Search className="w-5 h-5 text-gray-600" />
        </button>
        
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
          title="노트"
        >
          <Pencil className="w-5 h-5 text-gray-600" />
        </button>
        
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
          title="AI 요약"
        >
          <Sparkles className="w-5 h-5 text-gray-600" />
        </button>
        
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
          title="분석"
        >
          <BarChart className="w-5 h-5 text-gray-600" />
        </button>
        
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 transition-colors"
          title="문서"
        >
          <FileText className="w-5 h-5 text-gray-900" />
        </button>
      </nav>

      {/* 하단 아이콘 - 회색 */}
      <div className="flex flex-col items-center space-y-4">
        <button 
          className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-200 hover:bg-gray-300 transition-colors"
          title="내 프로필"
        >
          <AlanIcon width={12} height={16} className="text-gray-700" />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
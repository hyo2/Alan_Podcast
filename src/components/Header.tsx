// src/components/Header.tsx
import { Bell, User, Menu } from 'lucide-react';
import AlanLogo from './AlanLogo';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

const Header = ({ onToggleSidebar }: HeaderProps) => {
  return (
    <header className="fixed top-0 left-16 right-0 h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 z-40">
      {/* Left: Alan Logo */}
      <div className="flex items-center gap-4">
        <button 
          onClick={onToggleSidebar}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors lg:hidden"
        >
          <Menu className="w-5 h-5 text-gray-700" />
        </button>
        
        <AlanLogo width={75} height={20} className="text-gray-900" />
      </div>
      
      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Upgrade Button - 깔끔한 파란색 */}
        <button className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors">
          <span className="hidden sm:inline">Alan Pro로 업그레이드</span>
          <span className="sm:hidden">Pro</span>
        </button>
        
        {/* Notifications */}
        <button className="p-2 hover:bg-gray-100 rounded-lg relative transition-colors">
          <Bell className="w-5 h-5 text-gray-600" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full"></span>
        </button>
        
        {/* User Avatar - 회색 */}
        <button className="w-9 h-9 rounded-full flex items-center justify-center bg-gray-200 hover:bg-gray-300 transition-colors">
          <User className="w-5 h-5 text-gray-700" />
        </button>
      </div>
    </header>
  );
};

export default Header;
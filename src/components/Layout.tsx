// src/components/Layout.tsx
import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

interface LayoutProps {
  children: React.ReactNode;  // ReactNode 대신 React.ReactNode
}

const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="h-screen flex bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col ml-16">
        <Header />
        <main className="flex-1 overflow-auto pt-16">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
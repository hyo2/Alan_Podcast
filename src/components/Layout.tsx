import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import ProjectSidebar from "../components/ProjectSidebar";
import { Outlet } from "react-router-dom";

export default function Layout() {
  const [openProjects, setOpenProjects] = useState(false);

  return (
    <div className="flex">
      <Sidebar onOpenProjects={() => setOpenProjects(true)} />

      {/* Project List Sidebar */}
      {openProjects && (
        <ProjectSidebar
          open={openProjects}
          onClose={() => setOpenProjects(false)}
        />
      )}

      <div className="flex-1 pl-[60px]">
        {" "}
        {/* 사이드바 너비만큼 패딩 추가 */}
        <Header />
        <main className="mt-16 p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

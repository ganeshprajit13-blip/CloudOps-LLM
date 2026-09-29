import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import HeaderNav from './HeaderNav';
import Sidebar from './Sidebar';
import SidebarDrawer from './SidebarDrawer';

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleSidebar = () => {
    if (window.innerWidth < 1024) {
      setMobileOpen((prev) => !prev);
    } else {
      setCollapsed((prev) => !prev);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] text-[#0F172A] font-sans antialiased relative overflow-x-hidden">
      {/* 1. DESKTOP SIDEBAR & MOBILE DRAWER */}
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />

      {/* 2. MOBILE DRAWER OVERLAY */}
      <SidebarDrawer
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />

      {/* 3. STICKY HEADER */}
      <HeaderNav
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggleSidebar={toggleSidebar}
      />

      {/* 4. MAIN SCROLLABLE CONTENT AREA */}
      <div
        className={`pt-16 min-h-screen flex-1 flex flex-col transition-all duration-300 ease-in-out ${
          collapsed ? 'lg:ml-20 w-full lg:w-[calc(100%-5rem)]' : 'lg:ml-64 w-full lg:w-[calc(100%-16rem)]'
        }`}
      >
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

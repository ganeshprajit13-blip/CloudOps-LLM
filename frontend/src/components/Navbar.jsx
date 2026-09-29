import React, { useState } from 'react';
import {
  Search,
  Bell,
  Sun,
  Moon,
  Cloud,
  CheckCircle2,
  AlertTriangle,
  Menu,
  User,
  Shield,
  RefreshCw
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { getApiBaseUrl } from '../api/axios';

export default function Navbar({ setMobileOpen }) {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const notifications = [
    { id: 1, title: 'Critical Alert: Port 443 Blocked', time: '10m ago', type: 'critical' },
    { id: 2, title: 'EC2 CPU Spike on i-0d5e6f', time: '45m ago', type: 'warning' },
    { id: 3, title: 'RAG Knowledge Index Updated', time: '2h ago', type: 'info' }
  ];

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 800);
  };

  const baseUrl = getApiBaseUrl();
  const isLocal = baseUrl.includes('localhost') || baseUrl.includes('127.0.0.1');

  return (
    <header className="sticky top-0 z-30 h-16 glass-panel border-b border-slate-800/80 px-4 lg:px-8 flex items-center justify-between">
      {/* Left section: Mobile menu & Search */}
      <div className="flex items-center space-x-4 flex-1 max-w-xl">
        <button
          onClick={() => setMobileOpen(true)}
          className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="relative w-full max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search resources, incidents, logs or AI diagnoses... (Ctrl+K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-1.5 text-xs lg:text-sm rounded-xl bg-slate-900/60 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        </div>
      </div>

      {/* Right section: Status & Controls */}
      <div className="flex items-center space-x-3">
        {/* AWS Connection Status */}
        <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-800 text-xs">
          <Cloud className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-slate-400">AWS Region:</span>
          <span className="font-semibold text-emerald-400 flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
            <span>us-east-1</span>
          </span>
          <button
            onClick={handleRefresh}
            title="Refresh Connection"
            className="p-0.5 text-slate-400 hover:text-cyan-400 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Backend Connection Target Pill */}
        <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-indigo-950/40 border border-indigo-500/30 text-[11px] text-indigo-300">
          <Shield className="w-3 h-3 text-indigo-400" />
          <span className="truncate max-w-[140px]" title={baseUrl}>
            Backend: {isLocal ? 'FastAPI (Local)' : baseUrl.replace('http://', '').replace('https://', '')}
          </span>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-400" />
          )}
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors relative"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-slate-900" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-2xl glass-panel border border-slate-800 shadow-2xl p-4 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">Notifications</h4>
                <span className="px-2 py-0.5 text-[10px] bg-cyan-500/20 text-cyan-300 font-bold rounded-full">
                  3 New
                </span>
              </div>
              <div className="space-y-2.5">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/60 hover:border-slate-700 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <p className="text-xs font-medium text-slate-200">{n.title}</p>
                      <span className="text-[10px] text-slate-500">{n.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* User Profile */}
        <div className="flex items-center space-x-2 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 p-[1px]">
            <div className="w-full h-full rounded-[11px] bg-slate-950 flex items-center justify-center font-bold text-xs text-cyan-300">
              {user?.name ? user.name.slice(0, 2).toUpperCase() : 'OP'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

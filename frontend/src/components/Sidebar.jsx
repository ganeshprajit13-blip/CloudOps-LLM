import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Terminal,
  Bot,
  MessageSquare,
  History,
  Settings,
  LogOut,
  ShieldCheck,
  Zap,
  ChevronRight,
  X
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useLanguage } from '../context/LanguageContext';
import CloudOpsMark from './CloudOpsMark';

const mainNavItems = [
  { path: '/dashboard', key: 'dashboard', defaultLabel: 'Dashboard', icon: LayoutDashboard },
  { path: '/troubleshoot', key: 'troubleshooter', defaultLabel: 'AI Troubleshooter', icon: Bot, highlight: true },
  { path: '/support-agent', key: 'supportAgent', defaultLabel: 'Support Agent', icon: MessageSquare, highlight: true },
  { path: '/resources', key: 'resources', defaultLabel: 'Cloud Resources', icon: Server },
  { path: '/logs', key: 'logs', defaultLabel: 'Logs', icon: Terminal },
  { path: '/history', key: 'history', defaultLabel: 'Analysis History', icon: History },
  { path: '/settings', key: 'settings', defaultLabel: 'Settings', icon: Settings },
];

export default function Sidebar({ collapsed, mobileOpen, setMobileOpen }) {
  const { logout, user } = useAuth();
  const { profile, initials } = useProfile();
  const { t } = useLanguage();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed top-0 left-0 z-50 h-screen bg-white border-r border-slate-200/80 shadow-xs flex flex-col justify-between transition-all duration-300 ease-in-out select-none ${
          collapsed ? 'w-20' : 'w-64'
        } ${
          mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div>
          {/* Header & Logo */}
          <div className={`flex items-center justify-between h-16 border-b border-slate-100 ${collapsed ? 'px-3 justify-center' : 'px-5'}`}>
            <NavLink to="/dashboard" className="flex items-center space-x-3 truncate">
              <CloudOpsMark size={40} />
              {!collapsed && (
                <div className="leading-tight truncate">
                  <span className="font-extrabold text-base text-slate-900 tracking-tight block">
                    CloudOps LLM
                  </span>
                  <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">
                    Cloud Trouble Shooter
                  </span>
                </div>
              )}
            </NavLink>

            <button
              onClick={() => setMobileOpen(false)}
              className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Menu */}
          <nav className="px-3 py-4 space-y-1 overflow-y-auto max-h-[calc(100vh-170px)]">
            {!collapsed && (
              <div className="px-3 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                {t('navigation')}
              </div>
            )}
            {mainNavItems.map((item) => {
              const Icon = item.icon;
              const labelText = t(item.key) || item.defaultLabel;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  title={collapsed ? labelText : undefined}
                  className={({ isActive }) =>
                    `flex items-center ${collapsed ? 'justify-center px-0 py-2.5' : 'justify-between px-3.5 py-2.5'} rounded-xl text-xs font-semibold transition-all duration-150 group ${
                      isActive
                        ? 'bg-slate-900 text-white font-bold shadow-2xs'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div className="flex items-center space-x-3">
                        <Icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-900'}`} />
                        {!collapsed && <span>{labelText}</span>}
                      </div>

                      {!collapsed && (
                        <div className="flex items-center space-x-1">
                          {item.badge && (
                            <span className={`px-2 py-0.5 text-[10px] font-extrabold rounded-full ${isActive ? 'bg-rose-500 text-white' : 'bg-rose-50 text-rose-600 border border-rose-100'}`}>
                              {item.badge}
                            </span>
                          )}
                          {item.highlight && (
                            <span className={`px-1.5 py-0.5 text-[9px] font-extrabold uppercase rounded ${isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700 border border-slate-200'}`}>
                              AI
                            </span>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* User Profile Card at Bottom */}
        <div className={`p-3 border-t border-slate-100 bg-slate-50/50 ${collapsed ? 'flex flex-col items-center space-y-2' : ''}`}>
          {!collapsed ? (
            <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/70 shadow-2xs">
              <div className="flex items-center space-x-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-slate-900 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-2xs">
                  {profile?.avatar_url ? (
                    <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover rounded-full" />
                  ) : (
                    <span>{initials}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-900 truncate">
                    {profile?.display_name || user?.name || 'Ganesh'}
                  </p>
                  <p className="text-[10px] font-medium text-slate-500 truncate">
                    {profile?.role || 'DevOps Engineer'}
                  </p>
                </div>
              </div>

              <button
                onClick={handleLogout}
                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={handleLogout}
              className="w-10 h-10 rounded-full bg-slate-100 hover:bg-rose-50 hover:text-rose-600 text-slate-600 flex items-center justify-center transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </aside>
    </>
  );
}

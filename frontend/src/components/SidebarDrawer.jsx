import React, { useState, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Terminal,
  Bot,
  MessageSquare,
  History,
  Settings,
  ChevronRight,
  LogOut,
  X,
  User,
  Edit3,
  Camera,
} from 'lucide-react';
import CloudOpsMark from './CloudOpsMark';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useLanguage } from '../context/LanguageContext';

/* ─────────────────────────────────────────────
   Navigation definition
───────────────────────────────────────────── */
const mainNavItems = [
  { path: '/dashboard',      key: 'dashboard',      defaultLabel: 'Dashboard',         icon: LayoutDashboard, tier: 'normal' },
  { path: '/troubleshoot',   key: 'troubleshooter', defaultLabel: 'AI Troubleshooter', icon: Bot,             tier: 'primary', badge: 'AI' },
  { path: '/support-agent',  key: 'supportAgent',   defaultLabel: 'Support Agent',     icon: MessageSquare,   tier: 'secondary', badge: 'AI' },
  { path: '/resources',      key: 'resources',      defaultLabel: 'Cloud Resources',   icon: Server,          tier: 'normal' },
  { path: '/logs',           key: 'logs',           defaultLabel: 'Logs',              icon: Terminal,        tier: 'quiet' },
  { path: '/history',        key: 'history',        defaultLabel: 'Analysis History',  icon: History,         tier: 'quiet' },
];

/* ─────────────────────────────────────────────
   Avatar component — photo or initials
───────────────────────────────────────────── */
function Avatar({ src, initials, size = 40, ring = false, className = '' }) {
  const sz = `w-[${size}px] h-[${size}px]`;
  return (
    <div
      className={`relative rounded-full shrink-0 overflow-hidden flex items-center justify-center
        ${ring ? 'ring-2 ring-[#0284C7]/40 ring-offset-1' : ''}
        ${className}`}
      style={{ width: size, height: size }}
    >
      {src ? (
        <img src={src} alt="Avatar" className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full bg-gradient-to-br from-[#0284C7] to-[#0891B2] flex items-center justify-center text-white font-bold select-none"
          style={{ fontSize: size * 0.36 }}>
          {initials}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Profile card with flyout menu
───────────────────────────────────────────── */
function ProfileCard({ onClose }) {
  const { profile, initials } = useProfile();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleSignOut = async () => {
    setMenuOpen(false);
    onClose();
    await logout();
    navigate('/login');
  };

  const handleNavigate = (path) => {
    setMenuOpen(false);
    onClose();
    navigate(path);
  };

  return (
    <div className="relative">
      {/* Card */}
      <button
        onClick={() => setMenuOpen((v) => !v)}
        className="w-full group flex items-center space-x-3 px-3.5 py-3 rounded-2xl
          bg-[#F0F7FF] hover:bg-[#E0F2FE]
          border border-[#BAE6FD] hover:border-[#0284C7]/40
          shadow-xs hover:shadow-md
          transition-all duration-200 text-left"
      >
        <Avatar
          src={profile?.avatar_url}
          initials={initials}
          size={38}
          ring
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-[#0F172A] truncate leading-tight">
            {profile?.display_name || 'Cloud User'}
          </p>
          <p className="text-[11px] text-[#0369A1] font-medium truncate mt-0.5">
            {profile?.role || 'Cloud Engineer'}
          </p>
        </div>
        <ChevronRight className={`w-4 h-4 text-[#0369A1] shrink-0 transition-transform duration-200 ${menuOpen ? 'rotate-90' : 'group-hover:translate-x-0.5'}`} />
      </button>

      {/* Flyout menu */}
      {menuOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-2 rounded-2xl bg-white border border-[#BAE6FD] shadow-xl p-2 z-50 space-y-0.5 text-[#0F172A]">
          {/* User info header */}
          <div className="px-3 py-2.5 border-b border-[#E2E8F0] mb-1.5">
            <p className="text-xs font-bold text-[#0F172A] truncate">{profile?.display_name || 'Cloud User'}</p>
            <p className="text-[11px] text-[#64748B] truncate">{profile?.email || ''}</p>
          </div>

          <button
            onClick={() => handleNavigate('/profile')}
            className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-[#0F172A] hover:bg-[#F0F7FF] transition-all"
          >
            <User className="w-4 h-4 text-[#0284C7]" />
            <span>View Profile</span>
          </button>

          <button
            onClick={() => handleNavigate('/profile')}
            className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-[#0F172A] hover:bg-[#F0F7FF] transition-all"
          >
            <Edit3 className="w-4 h-4 text-[#0284C7]" />
            <span>Edit Profile</span>
          </button>

          <button
            onClick={() => handleNavigate('/settings')}
            className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-[#0F172A] hover:bg-[#F0F7FF] transition-all"
          >
            <Settings className="w-4 h-4 text-[#0284C7]" />
            <span>Settings</span>
          </button>

          <div className="pt-1.5 border-t border-[#E2E8F0] mt-1">
            <button
              onClick={handleSignOut}
              className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-all"
            >
              <LogOut className="w-4 h-4 text-rose-500" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Nav item
───────────────────────────────────────────── */
function NavItem({ item, onClose }) {
  const { t } = useLanguage();
  const Icon = item.icon;
  const labelText = t(item.key) || item.defaultLabel;

  return (
    <NavLink
      to={item.path}
      onClick={onClose}
      className={({ isActive }) => {
        const base = 'flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-all duration-150 group';
        if (isActive) {
          return `${base} bg-slate-900 text-white font-bold shadow-xs`;
        }
        return `${base} text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-semibold`;
      }}
    >
      {({ isActive }) => (
        <>
          <div className="flex items-center space-x-3">
            <Icon
              className={`w-4 h-4 shrink-0 transition-colors ${
                isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-900'
              }`}
              strokeWidth={item.tier === 'primary' ? 2.2 : 1.8}
            />
            <span className={`truncate ${isActive ? 'text-white' : 'text-slate-800'}`}>
              {labelText}
            </span>
          </div>

          <div className="flex items-center space-x-1.5 shrink-0">
            {item.count && (
              <span className={`px-1.5 py-0.5 text-[9px] font-extrabold rounded-full leading-none ${
                isActive ? 'bg-white/20 text-white' : 'bg-slate-800 text-white'
              }`}>
                {item.count}
              </span>
            )}
            {item.badge === 'AI' && (
              <span className={`px-1.5 py-0.5 text-[9px] font-extrabold uppercase rounded leading-none ${
                isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}>
                AI
              </span>
            )}
          </div>
        </>
      )}
    </NavLink>
  );
}

/* ─────────────────────────────────────────────
   Main Sidebar Drawer
───────────────────────────────────────────── */
export default function SidebarDrawer({ isOpen, onClose }) {
  const { t } = useLanguage();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-xs lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 left-0 z-50 flex flex-col h-screen w-[272px]
          bg-white border-r border-slate-200 shadow-xl
          transition-transform duration-300 ease-in-out select-none
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* ── BRAND HEADER ─────────────────────────────── */}
        <div className="px-5 pt-6 pb-5 border-b border-[#E2E8F0]">
          <div className="flex items-start justify-between">
            {/* Logo + Wordmark */}
            <div className="flex items-center space-x-3 group">
              <div className="transition-transform duration-200 group-hover:scale-105">
                <CloudOpsMark size={46} />
              </div>
              <div className="leading-none">
                <span className="block text-[17px] font-extrabold tracking-tight text-[#0F172A] leading-none">
                  CloudOps
                </span>
                <span className="block text-[11px] font-semibold text-slate-500 mt-1 tracking-wide">
                  AI Cloud Platform
                </span>
              </div>
            </div>

            {/* Close button — mobile */}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[#F1F5F9] text-[#94A3B8] hover:text-[#0F172A] transition-colors -mt-0.5 -mr-1"
              title="Close"
              aria-label="Close navigation"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── NAVIGATION ───────────────────────────────── */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          {/* Section label */}
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-[#94A3B8]">
            Navigation
          </p>

          {mainNavItems.map((item) => (
            <NavItem key={item.path} item={item} onClose={onClose} />
          ))}

          {/* Settings - quieter at the bottom */}
          <div className="pt-2 mt-2 border-t border-[#E2E8F0]">
            <NavLink
              to="/settings"
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-slate-900 text-white font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Settings className={`w-4 h-4 ${isActive ? 'text-white' : 'opacity-70'}`} strokeWidth={1.8} />
                  <span className={isActive ? 'text-white' : ''}>Settings</span>
                </>
              )}
            </NavLink>
          </div>
        </nav>

        {/* ── PROFILE CARD ─────────────────────────────── */}
        <div className="px-3 pb-4 pt-3 border-t border-[#E2E8F0]">
          <ProfileCard onClose={onClose} />
        </div>
      </aside>
    </>
  );
}

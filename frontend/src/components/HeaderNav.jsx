import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  X,
  Search,
  Bell,
  User,
  ChevronDown,
  Globe,
  LogOut,
  Mail,
  Bot,
  Check,
  ArrowRight,
  Menu
} from 'lucide-react';
import CloudOpsMark from './CloudOpsMark';
import ContactUsModal from './ContactUsModal';
import SupportChatbotModal from './SupportChatbotModal';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useLanguage } from '../context/LanguageContext';

const languagesList = [
  { code: 'en', name: 'English (US)', flag: '🇺🇸' },
  { code: 'es', name: 'Español (Spanish)', flag: '🇪🇸' },
  { code: 'fr', name: 'Français (French)', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch (German)', flag: '🇩🇪' },
  { code: 'ja', name: '日本語 (Japanese)', flag: '🇯🇵' },
  { code: 'zh', name: '中文 (Chinese)', flag: '🇨🇳' },
  { code: 'hi', name: 'हिन्दी (Hindi)', flag: '🇮🇳' },
  { code: 'ta', name: 'தமிழ் (Tamil)', flag: '🇮🇳' }
];

const searchableItems = [
  { title: 'Cloud Resources Overview', category: 'Page', link: '/resources' },
  { title: 'System & Cluster Logs', category: 'Page', link: '/logs' },
  { title: 'Incidents & Active Alerts', category: 'Page', link: '/incidents' },
  { title: 'AI Troubleshooter & Diagnostics', category: 'Page', link: '/troubleshoot' },
  { title: 'RAG Analysis History', category: 'Page', link: '/history' },
  { title: 'Vector Store Knowledge Base', category: 'Page', link: '/knowledge' },
  { title: 'Cloud Billing & Usage Cost', category: 'Page', link: '/billing' },
  { title: 'Settings & Integrations', category: 'Page', link: '/settings' },
  { title: 'EC2 Web Server (i-0d5e6f8a1b2c3d4e)', category: 'Resource', link: '/resources?q=i-0d5e6f8a1b2c3d4e' },
  { title: 'RDS PostgreSQL Database Cluster', category: 'Resource', link: '/resources?q=db-prod-pg-cluster' },
  { title: 'Critical Alert: Port 443 Security Group Blocked', category: 'Incident', link: '/incidents' },
  { title: 'Database Connection Timeout Logs', category: 'Log', link: '/logs?q=Timeout' },
  { title: 'Out of Memory (OOMKilled) Container Logs', category: 'Log', link: '/logs?q=OOMKilled' },
];

export default function HeaderNav({ collapsed, mobileOpen, onToggleSidebar }) {
  const { logout, user } = useAuth();
  const { profile, initials } = useProfile();
  const { language, changeLanguage, t } = useLanguage();
  const navigate = useNavigate();

  const [showLangMenu, setShowLangMenu] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [showSupportModal, setShowSupportModal] = useState(false);

  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const filteredSearchItems = searchQuery.trim()
    ? searchableItems.filter((item) =>
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.category.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  const handleSearchSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!searchQuery.trim()) return;
    const query = searchQuery.trim();
    setIsSearchFocused(false);
    
    if (query.toLowerCase().includes('log') || query.toLowerCase().includes('error') || query.toLowerCase().includes('timeout')) {
      navigate(`/logs?q=${encodeURIComponent(query)}`);
    } else {
      navigate(`/resources?q=${encodeURIComponent(query)}`);
    }
  };

  const handleItemClick = (link) => {
    setIsSearchFocused(false);
    navigate(link);
  };

  const notifications = [
    { id: 1, title: 'Critical Alert: Port 443 Blocked', time: '10m ago' },
    { id: 2, title: 'EC2 CPU Spike on i-0d5e6f', time: '45m ago' },
    { id: 3, title: 'RAG Knowledge Index Updated', time: '2h ago' }
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSelectLang = (langName) => {
    changeLanguage(langName);
    setShowLangMenu(false);
  };

  return (
    <>
      <header
        className={`fixed top-0 right-0 z-40 bg-white/95 border-b border-slate-200/80 backdrop-blur-md shadow-2xs select-none transition-all duration-300 ease-in-out ${
          collapsed ? 'left-0 lg:left-20' : 'left-0 lg:left-64'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-3 sm:gap-6">
            
            {/* 1. SIDEBAR TOGGLE & CLOUDOPS TITLE */}
            <div className="flex items-center space-x-3 shrink-0">
              <button
                onClick={onToggleSidebar}
                className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors flex items-center justify-center border border-slate-200 cursor-pointer"
                title="Toggle Sidebar"
                aria-label="Toggle Sidebar"
              >
                <Menu className="w-4 h-4 text-slate-800" />
              </button>

              <span className="font-extrabold text-lg text-slate-900 tracking-tight block">
                CloudOps
              </span>
            </div>

            {/* 2. SEARCH BAR */}
            <div className="relative hidden md:block flex-1 max-w-lg">
              <form onSubmit={handleSearchSubmit} className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search your infrastructure, logs, incidents, or ask anything..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setIsSearchFocused(true);
                  }}
                  onFocus={() => setIsSearchFocused(true)}
                  onBlur={() => setTimeout(() => setIsSearchFocused(false), 200)}
                  className="w-full pl-10 pr-16 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white font-medium transition-all shadow-2xs"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center space-x-1 pointer-events-none">
                  <span className="text-[10px] font-bold text-slate-400 bg-slate-200/80 px-1.5 py-0.5 rounded border border-slate-300/60">
                    Ctrl K
                  </span>
                </div>
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="absolute right-14 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-700"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </form>

              {/* Live Search Dropdown */}
              {isSearchFocused && searchQuery.trim().length > 0 && (
                <div className="absolute left-0 right-0 mt-2 rounded-2xl bg-white border border-slate-200 shadow-xl p-2 z-50 text-slate-900 max-h-80 overflow-y-auto">
                  <div className="px-3 py-1.5 text-[10px] uppercase font-bold text-slate-400 border-b border-slate-100 flex items-center justify-between">
                    <span>Search Results</span>
                    <span className="text-[9px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-bold">Press Enter</span>
                  </div>

                  {filteredSearchItems.length > 0 ? (
                    <div className="space-y-1 pt-1.5">
                      {filteredSearchItems.map((item, idx) => (
                        <button
                          key={idx}
                          onMouseDown={() => handleItemClick(item.link)}
                          className="w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between hover:bg-slate-50 transition-colors group cursor-pointer"
                        >
                          <div className="flex items-center space-x-2 truncate">
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 shrink-0 border border-blue-100">
                              {item.category}
                            </span>
                            <span className="font-semibold text-slate-800 group-hover:text-blue-600 truncate">
                              {item.title}
                            </span>
                          </div>
                          <ArrowRight className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2" />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-xs text-slate-500">
                      No exact matches found for "{searchQuery}".
                      <button
                        onMouseDown={() => handleSearchSubmit({ preventDefault: () => {} })}
                        className="mt-2 block w-full text-center py-1.5 px-3 bg-blue-50 text-blue-600 font-bold rounded-xl text-xs hover:bg-blue-100 transition-colors"
                      >
                        Search in Resources
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 3. RIGHT HEADER CONTROLS */}
            <div className="flex items-center space-x-3 sm:space-x-4 text-xs font-semibold text-slate-700">
              
              {/* Language Selector */}
              <div className="relative">
                <button
                  onClick={() => setShowLangMenu(!showLangMenu)}
                  className="hover:text-blue-600 flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl hover:bg-slate-100 transition-colors text-xs font-semibold text-slate-700 cursor-pointer border border-transparent hover:border-slate-200"
                >
                  <Globe className="w-4 h-4 text-blue-600" />
                  <span className="flex items-center space-x-1">
                    <span>{languagesList.find(l => l.name === language)?.flag || '🌐'}</span>
                    <span>{language.split(' ')[0]}</span>
                  </span>
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                </button>

                {showLangMenu && (
                  <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white border border-slate-200 shadow-xl p-2 z-50 text-slate-900 animate-in fade-in zoom-in-95 duration-150">
                    <div className="px-3 py-1.5 text-[10px] uppercase font-bold text-slate-400 border-b border-slate-100 flex items-center justify-between">
                      <span>{t('selectLanguage')}</span>
                      <Globe className="w-3.5 h-3.5 text-slate-400" />
                    </div>
                    <div className="space-y-0.5 pt-1 max-h-64 overflow-y-auto">
                      {languagesList.map((lang) => (
                        <button
                          key={lang.code}
                          onClick={() => handleSelectLang(lang.name)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-colors cursor-pointer ${
                            language === lang.name
                              ? 'bg-blue-50 text-blue-600 font-bold'
                              : 'hover:bg-slate-50 text-slate-700'
                          }`}
                        >
                          <span className="flex items-center space-x-2">
                            <span className="text-sm">{lang.flag}</span>
                            <span>{lang.name}</span>
                          </span>
                          {language === lang.name && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Contact Us Trigger */}
              <button
                onClick={() => setShowContactModal(true)}
                className="text-slate-700 hover:text-blue-600 cursor-pointer hidden sm:flex items-center space-x-1 text-xs font-semibold transition-colors px-2 py-1 rounded-lg hover:bg-slate-50"
              >
                <span>{t('contactUs')}</span>
              </button>

              {/* AWS Marketplace */}
              <span className="text-slate-700 hover:text-blue-600 cursor-pointer hidden lg:inline text-xs font-semibold transition-colors px-2 py-1 rounded-lg hover:bg-slate-50">
                {t('awsMarketplace')}
              </span>

              {/* Notifications */}
              <div className="relative">
                <button
                  onClick={() => setShowNotifications(!showNotifications)}
                  className="p-1.5 rounded-xl text-slate-700 hover:bg-slate-100 transition-colors relative flex items-center justify-center cursor-pointer"
                  title="Notifications"
                >
                  <Bell className="w-4 h-4 text-slate-600" />
                  <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full" />
                </button>

                {showNotifications && (
                  <div className="absolute right-0 mt-2 w-72 rounded-2xl bg-white border border-slate-200 shadow-xl p-3.5 z-50 text-slate-900">
                    <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                      <span className="text-xs font-bold uppercase text-slate-500">Alert Notifications</span>
                      <span className="text-[10px] bg-blue-50 text-blue-600 font-bold px-2 py-0.5 rounded-full">3 New</span>
                    </div>
                    <div className="space-y-2">
                      {notifications.map((n) => (
                        <div key={n.id} className="p-2 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                          <p className="font-semibold text-slate-800">{n.title}</p>
                          <span className="text-[10px] text-slate-400">{n.time}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* User Account Menu */}
              <div className="relative border-l border-slate-200 pl-3">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center space-x-2 font-semibold text-slate-900 hover:text-blue-600 transition-colors text-xs cursor-pointer"
                >
                  <div className="w-8 h-8 rounded-full overflow-hidden bg-blue-600 text-white font-bold text-xs flex items-center justify-center shrink-0 border border-slate-200 shadow-2xs">
                    {profile?.avatar_url ? (
                      <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                    ) : (
                      <span>{initials}</span>
                    )}
                  </div>
                  <span className="hidden sm:inline font-bold text-slate-900">{profile?.display_name || user?.name || 'GANESH'}</span>
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                </button>

                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-60 rounded-2xl bg-white border border-slate-200 shadow-xl p-3 z-50 text-slate-900 space-y-1">
                    <div className="p-2.5 border-b border-slate-100 bg-slate-50 rounded-xl mb-1">
                      <p className="text-xs font-extrabold truncate text-slate-900">{profile?.display_name || user?.name || 'Ganesh'}</p>
                      <p className="text-[10px] font-semibold text-blue-600 truncate mt-0.5">{profile?.role || 'DevOps Engineer'}</p>
                      <p className="text-[10px] text-slate-400 truncate mt-0.5">{user?.email || 'ganesh@cloudops.ai'}</p>
                    </div>

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        navigate('/profile');
                      }}
                      className="w-full flex items-center space-x-2 p-2 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                    >
                      <User className="w-4 h-4 text-blue-600" />
                      <span>{t('viewProfile')}</span>
                    </button>

                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center space-x-2 p-2 rounded-xl text-xs font-bold text-rose-600 hover:bg-rose-50 transition-colors mt-1 border-t border-slate-100 pt-2 cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>{t('signOut')}</span>
                    </button>
                  </div>
                )}
              </div>

            </div>
          </div>
        </div>
      </header>

      {/* Modals */}
      <ContactUsModal isOpen={showContactModal} onClose={() => setShowContactModal(false)} />
      <SupportChatbotModal isOpen={showSupportModal} onClose={() => setShowSupportModal(false)} />
    </>
  );
}

import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Server,
  Cloud,
  Shield,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Save,
  Moon,
  Sun,
  Laptop
} from 'lucide-react';
import { getApiBaseUrl } from '../api/axios';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { dashboardApi } from '../api/dashboardApi';
import { Globe, Check } from 'lucide-react';

const languagesList = [
  { code: 'en', name: 'English (US)', flag: '🇺🇸', native: 'English' },
  { code: 'es', name: 'Español (Spanish)', flag: '🇪🇸', native: 'Español' },
  { code: 'fr', name: 'Français (French)', flag: '🇫🇷', native: 'Français' },
  { code: 'de', name: 'Deutsch (German)', flag: '🇩🇪', native: 'Deutsch' },
  { code: 'ja', name: '日本語 (Japanese)', flag: '🇯🇵', native: '日本語' },
  { code: 'zh', name: '中文 (Chinese)', flag: '🇨🇳', native: '简体中文' },
  { code: 'hi', name: 'हिन्दी (Hindi)', flag: '🇮🇳', native: 'हिन्दी' },
  { code: 'ta', name: 'தமிழ் (Tamil)', flag: '🇮🇳', native: 'தமிழ்' }
];

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();
  const { language, changeLanguage, t } = useLanguage();
  
  const [apiBaseUrl, setApiBaseUrl] = useState(getApiBaseUrl());
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState(null);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    handleTestConnection();
  }, []);

  const handleSaveApiUrl = (e) => {
    e.preventDefault();
    localStorage.setItem('cloudops_api_base_url', apiBaseUrl.trim());
    setSaveMsg('Backend Target URL updated successfully!');
    setTimeout(() => setSaveMsg(''), 3000);
    handleTestConnection();
  };

  const handleTestConnection = async () => {
    setPinging(true);
    setPingResult(null);
    const start = Date.now();

    try {
      const res = await dashboardApi.getHealthStatus();
      const latency = Date.now() - start;

      if (res && res.backendConnected) {
        setPingResult({
          success: true,
          latency: `${latency} ms`,
          message: 'Successfully reached FastAPI backend!'
        });
      } else {
        setPingResult({
          success: false,
          message: 'Backend connection unavailable. Running in Demo/Fallback mode.'
        });
      }
    } catch (err) {
      setPingResult({
        success: false,
        message: 'Backend connection unavailable. Running in Demo/Fallback mode.'
      });
    } finally {
      setPinging(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300 max-w-4xl mx-auto">
      {/* PAGE HEADER */}
      <div className="pb-6 border-b border-[#E2E8F0]">
        <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
          {t('settingsTitle')}
        </h1>
        <p className="text-xs sm:text-sm text-[#64748B] font-normal mt-1">
          {t('settingsSubtitle')}
        </p>
      </div>

      {saveMsg && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-bold animate-in fade-in flex items-center space-x-2 shadow-xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{saveMsg}</span>
        </div>
      )}

      {/* 0. Language & Localization Preference Card */}
      <div className="bg-white p-6 sm:p-7 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-5">
        <div className="flex items-center space-x-3 border-b border-[#E2E8F0] pb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
            <Globe className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">{t('languageSettings')}</h2>
            <p className="text-xs text-[#64748B]">{t('languageSettingsDesc')}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
          {languagesList.map((lang) => {
            const isSelected = language === lang.name;
            return (
              <button
                key={lang.code}
                onClick={() => {
                  changeLanguage(lang.name);
                  setSaveMsg(`Language updated to ${lang.name}!`);
                  setTimeout(() => setSaveMsg(''), 3000);
                }}
                className={`p-3.5 rounded-2xl border text-left transition-all duration-150 flex items-center justify-between cursor-pointer ${
                  isSelected
                    ? 'bg-blue-50/80 border-blue-500 text-blue-900 ring-2 ring-blue-500/20 shadow-xs'
                    : 'bg-[#F8FAFC] hover:bg-slate-100 border-[#E2E8F0] text-slate-700'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <span className="text-xl">{lang.flag}</span>
                  <div>
                    <span className="text-xs font-bold block">{lang.name.split(' ')[0]}</span>
                    <span className="text-[10px] text-slate-400 font-medium block">{lang.native}</span>
                  </div>
                </div>
                {isSelected && (
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0">
                    <Check className="w-3 h-3" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 1. FastAPI Backend Connection Configuration */}
      <div className="bg-white p-6 sm:p-7 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-6">
        <div className="flex items-center space-x-3 border-b border-[#E2E8F0] pb-4">
          <div className="w-10 h-10 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD]/80 flex items-center justify-center text-[#0284C7]">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">{t('backendUrlTitle')}</h2>
            <p className="text-xs text-[#64748B]">{t('backendUrlDesc')}</p>
          </div>
        </div>

        <form onSubmit={handleSaveApiUrl} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-[#0F172A] uppercase tracking-wider block">
              VITE_API_BASE_URL Target
            </label>
            <div className="flex gap-3">
              <input
                type="text"
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrl(e.target.value)}
                placeholder="http://192.168.1.10:8000"
                className="flex-1 px-4 py-2.5 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0284C7] font-mono text-xs font-bold focus:outline-none focus:border-[#0284C7]"
              />
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-[#0284C7] hover:bg-[#0369A1] text-white font-bold text-xs shadow-xs transition-all flex items-center space-x-1.5 border border-[#0284C7]/20"
              >
                <Save className="w-4 h-4" />
                <span>Save Endpoint</span>
              </button>
            </div>
          </div>
        </form>

        {/* Backend Ping & Diagnostic Tool */}
        <div className="p-4 sm:p-5 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <RefreshCw className={`w-4 h-4 text-[#0284C7] ${pinging ? 'animate-spin' : ''}`} />
              <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Backend Connectivity Tester</span>
            </div>
            <button
              onClick={handleTestConnection}
              disabled={pinging}
              className="px-3.5 py-1.5 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] text-xs font-semibold text-[#0284C7] border border-[#BAE6FD] transition-colors"
            >
              {pinging ? 'Pinging...' : 'Test Connection Now'}
            </button>
          </div>

          {pingResult && (
            <div className={`p-4 rounded-xl border text-xs space-y-2 ${
              pingResult.success
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border-rose-200 text-rose-800'
            }`}>
              <div className="flex items-center justify-between font-bold">
                <span>{pingResult.message}</span>
                {pingResult.latency && <span className="font-mono">{pingResult.latency}</span>}
              </div>

              {!pingResult.success && (
                <div className="space-y-1 text-[11px] text-rose-800/90 pt-2 border-t border-rose-200">
                  <p className="font-bold">⚠️ Connection Troubleshooting Checklist:</p>
                  <ul className="list-disc pl-4 space-y-0.5 font-normal">
                    <li>Verify Backend Laptop 2 is running FastAPI server on port 8000</li>
                    <li>Ensure both laptops are connected to the same Wi-Fi / LAN network</li>
                    <li>Verify Laptop 2 firewall allows incoming connections on port 8000</li>
                    <li>Confirm CORS origin in FastAPI includes this frontend URL</li>
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 2. AWS Region & Security Status */}
      <div className="bg-white p-6 sm:p-7 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
        <div className="flex items-center space-x-3 border-b border-[#E2E8F0] pb-3">
          <Cloud className="w-5 h-5 text-[#0284C7]" />
          <h2 className="text-base font-bold text-[#0F172A]">AWS Infrastructure Credentials & Region</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
            <span className="text-[#64748B] block mb-1">Target AWS Region</span>
            <span className="font-bold text-emerald-700 text-sm">us-east-1 (N. Virginia)</span>
          </div>

          <div className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
            <span className="text-[#64748B] block mb-1">AWS Access Key Handling</span>
            <span className="font-semibold text-[#0F172A]">Handled exclusively on Backend Laptop (Boto3)</span>
          </div>
        </div>
      </div>

      {/* 3. Theme Preferences */}
      <div className="bg-white p-6 sm:p-7 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
        <div className="flex items-center space-x-3 border-b border-[#E2E8F0] pb-3">
          <Sun className="w-5 h-5 text-amber-500" />
          <h2 className="text-base font-bold text-[#0F172A]">UI Display Theme</h2>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => setTheme('dark')}
            className={`p-4 rounded-2xl border font-semibold text-xs flex items-center justify-center space-x-3 transition-all ${
              theme === 'dark'
                ? 'bg-[#E0F2FE] border-[#BAE6FD] text-[#0284C7] font-bold shadow-xs'
                : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
            }`}
          >
            <Moon className="w-4 h-4 text-[#0284C7]" />
            <span>Dark Theme (Enterprise Dark)</span>
          </button>

          <button
            onClick={() => setTheme('light')}
            className={`p-4 rounded-2xl border font-semibold text-xs flex items-center justify-center space-x-3 transition-all ${
              theme === 'light'
                ? 'bg-[#E0F2FE] border-[#BAE6FD] text-[#0284C7] font-bold shadow-xs'
                : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
            }`}
          >
            <Sun className="w-4 h-4 text-amber-500" />
            <span>Light Theme (SaaS Clean)</span>
          </button>
        </div>
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Zap,
  ShieldCheck,
  MessageSquare,
  Users,
  ChevronDown,
  X,
  Sparkles,
  Globe,
  Check
} from 'lucide-react';
import cloudopsHeroImg from '../assets/cloudops-hero.png';
import aboutEngineerImg from '../assets/about-engineer.jpg';
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

// Social Icon SVGs for Footer
function LinkedInIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.45c-.89 0-1.61.72-1.61 1.61s.72 1.61 1.61 1.61 1.61-.72 1.61-1.61c0-.89-.72-1.61-1.61-1.61Z" />
    </svg>
  );
}

function GithubIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function TwitterIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function YoutubeIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

// Information Modal Dialog for Footer Links
function InfoModal({ isOpen, onClose, title, content, links }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 sm:p-8 border border-slate-200 relative transform transition-all animate-scaleUp">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors cursor-pointer"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900">{title}</h3>
            <p className="text-xs text-slate-500 font-medium">Cloud ops LLM Platform</p>
          </div>
        </div>

        <div className="text-sm text-slate-600 leading-relaxed space-y-3 mb-6">
          {content}
        </div>

        {links && links.length > 0 && (
          <div className="border-t border-slate-100 pt-4 mb-6">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Quick Navigation</h4>
            <div className="flex flex-wrap gap-2">
              {links.map((link, idx) => (
                <Link
                  key={idx}
                  to={link.to}
                  onClick={onClose}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium transition-all shadow-sm cursor-pointer"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}

// =========================================================================
// FAQ SECTION COMPONENT
// =========================================================================
const FAQ_ITEMS = [
  {
    id: 1,
    question: 'What is Cloud ops LLM?',
    answer:
      'Cloud ops LLM is an AI-powered cloud troubleshooting platform that helps engineers understand infrastructure problems, identify possible root causes, and receive step-by-step guidance for resolving cloud issues.',
  },
  {
    id: 2,
    question: 'How does the AI Troubleshooter work?',
    answer:
      'Describe your cloud issue or provide relevant logs and context. The AI analyzes the available information, identifies possible causes, explains the evidence, and provides recommended troubleshooting steps.',
  },
  {
    id: 3,
    question: 'What types of cloud problems can it help troubleshoot?',
    answer:
      'Cloud ops LLM can help investigate infrastructure, networking, compute, application, configuration, performance, and service-related problems.',
  },
  {
    id: 4,
    question: 'Who is Cloud ops LLM designed for?',
    answer:
      'It is designed for cloud engineers, developers, DevOps teams, and anyone who needs faster and clearer assistance when troubleshooting cloud infrastructure.',
  },
];

function FAQSection() {
  const [openId, setOpenId] = useState(null);

  const toggle = (id) => setOpenId((prev) => (prev === id ? null : id));

  return (
    <section
      id="faq-section"
      className="w-full py-12 sm:py-16 px-6 sm:px-12 lg:px-16 border-t border-slate-100"
    >
      <div className="max-w-3xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-8">
          <span className="text-xs sm:text-sm font-semibold uppercase tracking-widest text-slate-500 mb-3 block">
            FAQ
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 leading-tight mb-3">
            Frequently Asked Questions
          </h2>
          <p className="text-base text-slate-500 font-normal">
            Everything you need to know about Cloud ops LLM.
          </p>
        </div>

        {/* Accordion Items */}
        <div className="space-y-3">
          {FAQ_ITEMS.map((item) => {
            const isOpen = openId === item.id;
            return (
              <div
                key={item.id}
                className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden"
              >
                {/* Question Row */}
                <button
                  id={`faq-toggle-${item.id}`}
                  onClick={() => toggle(item.id)}
                  aria-expanded={isOpen}
                  className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left cursor-pointer group"
                >
                  <span className="text-sm sm:text-base font-semibold text-slate-900 leading-snug group-hover:text-[#0066FF] transition-colors duration-150">
                    {item.question}
                  </span>
                  <span
                    className="flex-shrink-0 w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 group-hover:border-[#0066FF] group-hover:text-[#0066FF] transition-all duration-150 text-lg font-light select-none"
                    aria-hidden="true"
                  >
                    {isOpen ? '−' : '+'}
                  </span>
                </button>

                {/* Answer — smooth expand */}
                <div
                  style={{
                    maxHeight: isOpen ? '300px' : '0px',
                    overflow: 'hidden',
                    transition: 'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  <p className="px-6 pb-5 text-sm sm:text-base text-slate-600 leading-relaxed">
                    {item.answer}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// =========================================================================
// MAIN HOMEPAGE COMPONENT
// =========================================================================
export default function Welcome() {
  const navigate = useNavigate();
  const { language, changeLanguage, t } = useLanguage();
  const [isScrolled, setIsScrolled] = useState(false);
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [modalState, setModalState] = useState({ isOpen: false, title: '', content: null, links: [] });

  React.useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 30);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToAbout = () => {
    const el = document.getElementById('about-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const openModal = (title, content, links = []) => {
    setModalState({ isOpen: true, title, content, links });
  };

  const closeModal = () => {
    setModalState({ isOpen: false, title: '', content: null, links: [] });
  };

  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans selection:bg-blue-600 selection:text-white relative overflow-x-hidden">
      
      {/* =========================================================
          1. STICKY SLIDE-DOWN HEADER (position: sticky, top: 0, zIndex: 1000)
          ========================================================= */}
      <header
        style={{ position: 'sticky', top: 0, zIndex: 1000 }}
        className={`w-full transition-all duration-300 ease-out px-6 sm:px-12 md:px-16 ${
          isScrolled
            ? 'bg-white/95 backdrop-blur-md shadow-md py-3.5 border-b border-slate-200/80 translate-y-0'
            : 'bg-white/80 backdrop-blur-xs py-5 border-b border-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Left: Brand name & subtitle */}
          <div className="flex flex-col select-none">
            <Link to="/" className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 hover:opacity-90 transition-opacity">
              Cloud ops LLM
            </Link>
            <span className="text-xs sm:text-sm font-medium text-slate-400 -mt-0.5">
              Cloud Trouble Shooter
            </span>
          </div>

          {/* Right: Language Selector & Functional Login & Sign Up CTA Buttons */}
          <div className="flex items-center gap-3 sm:gap-4">
            {/* Language Selector Dropdown */}
            <div className="relative">
              <button
                id="welcome-lang-btn"
                onClick={() => setShowLangMenu(!showLangMenu)}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200/80 transition-colors border border-slate-200 cursor-pointer"
                title={t('selectLanguage')}
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
                        onClick={() => {
                          changeLanguage(lang.name);
                          setShowLangMenu(false);
                        }}
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

            <button
              id="login-button-header"
              onClick={() => navigate('/login')}
              className="px-5 sm:px-6 py-2 rounded-lg text-sm font-semibold text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 hover:border-slate-400 shadow-xs transition-all duration-200 cursor-pointer"
            >
              {t('login')}
            </button>
            <button
              id="signup-button-header"
              onClick={() => navigate('/signup')}
              className="px-5 sm:px-6 py-2 rounded-lg text-sm font-semibold text-white bg-[#0066FF] hover:bg-[#0055D4] shadow-xs transition-all duration-200 cursor-pointer hover:shadow-sm"
            >
              {t('signUp')}
            </button>
          </div>
        </div>
      </header>

      {/* =========================================================
          2. FULL-SCREEN HERO SECTION (100vh)
             Rendering the exact original reference image directly
          ========================================================= */}
      <section className="relative w-full min-h-[calc(100vh-80px)] flex flex-col justify-between items-center px-4 sm:px-8 pt-2 pb-2 bg-white overflow-hidden">
        
        {/* Center Container with the exact reference image */}
        <div className="relative w-full max-w-6xl mx-auto flex-1 flex flex-col items-center justify-center">
          
          <div className="relative w-full max-w-5xl">
            {/* The exact original reference image as provided */}
            <img
              src={cloudopsHeroImg}
              alt="Cloud ops LLM - Cloud Trouble Shooter"
              className="w-full h-auto object-contain mx-auto select-none"
              priority="true"
            />
          </div>

        </div>

        {/* Explore More Smooth Scroll CTA */}
        <div className="w-full flex flex-col items-center justify-center pt-2 z-10 select-none">
          <button
            onClick={scrollToAbout}
            className="flex flex-col items-center gap-1 text-slate-400 hover:text-slate-700 transition-colors group cursor-pointer"
            aria-label="Scroll down to About section"
          >
            <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 group-hover:text-slate-600">
              {t('exploreMore')}
            </span>
            <ChevronDown className="w-4 h-4 animate-bounce group-hover:text-blue-600" />
          </button>
        </div>
      </section>

      {/* =========================================================
          3. ABOUT SECTION (Reference Image 2)
          ========================================================= */}
      <section
        id="about-section"
        className="w-full py-12 sm:py-16 px-6 sm:px-12 lg:px-16 max-w-7xl mx-auto border-t border-slate-100 transition-all"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          
          {/* Left Column: Headline, Description & 4 Features */}
          <div className="lg:col-span-6 flex flex-col justify-center">
            
            {/* Small Tag: ABOUT US */}
            <span className="text-xs sm:text-sm font-semibold uppercase tracking-widest text-slate-500 mb-3 block">
              {t('aboutUs')}
            </span>

            {/* Heading */}
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.18] mb-6">
              {t('smarterCloudOps')}
            </h2>

            {/* Description (5-6 visual lines) */}
            <div className="space-y-4 text-slate-600 text-base sm:text-lg leading-relaxed font-normal mb-10">
              <p>
                {t('smarterCloudOpsDesc')}
              </p>
              <p className="text-slate-500">
                {t('simplifyCloudOps')}
              </p>
            </div>

            {/* 4 Feature Highlights with simple line icons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-4 border-t border-slate-100">
              
              {/* 1. Faster Troubleshooting */}
              <div className="flex flex-col items-start gap-2">
                <Zap className="w-6 h-6 text-slate-900 stroke-[1.75]" />
                <div className="text-xs sm:text-sm font-semibold text-slate-900 leading-snug">
                  {t('fasterTroubleshooting')}
                </div>
              </div>

              {/* 2. Multi-Cloud Support */}
              <div className="flex flex-col items-start gap-2">
                <ShieldCheck className="w-6 h-6 text-slate-900 stroke-[1.75]" />
                <div className="text-xs sm:text-sm font-semibold text-slate-900 leading-snug">
                  {t('multiCloudSupport')}
                </div>
              </div>

              {/* 3. AI-Powered Insights */}
              <div className="flex flex-col items-start gap-2">
                <MessageSquare className="w-6 h-6 text-slate-900 stroke-[1.75]" />
                <div className="text-xs sm:text-sm font-semibold text-slate-900 leading-snug">
                  {t('aiInsights')}
                </div>
              </div>

              {/* 4. Built for Engineers */}
              <div className="flex flex-col items-start gap-2">
                <Users className="w-6 h-6 text-slate-900 stroke-[1.75]" />
                <div className="text-xs sm:text-sm font-semibold text-slate-900 leading-snug">
                  {t('builtForEngineers')}
                </div>
              </div>

            </div>

          </div>

          {/* Right Column: Person using laptop photo — tall portrait ratio */}
          <div className="lg:col-span-6 flex items-stretch justify-center">
            <div className="relative w-full overflow-hidden rounded-2xl sm:rounded-3xl shadow-xl border border-slate-200/80 bg-slate-50 group" style={{ minHeight: '520px' }}>
              <img
                src={aboutEngineerImg}
                alt="Cloud engineer using laptop outdoors"
                className="absolute inset-0 w-full h-full object-cover object-center transform transition-transform duration-700 ease-out group-hover:scale-[1.02]"
                loading="lazy"
              />
              <div className="absolute inset-0 ring-1 ring-inset ring-black/5 rounded-2xl sm:rounded-3xl pointer-events-none" />
            </div>
          </div>

        </div>
      </section>

      {/* =========================================================
          4. FAQ SECTION — above footer
          ========================================================= */}
      <FAQSection />

      {/* =========================================================
          5. FULL-WIDTH BLACK SAAS FOOTER (Reference Image 2)
          ========================================================= */}
      <footer className="w-full bg-[#000000] text-white pt-16 pb-12 px-6 sm:px-12 lg:px-16 border-t border-neutral-900">
        <div className="max-w-7xl mx-auto">
          
          {/* Main Footer Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-10 lg:gap-12 pb-14 border-b border-neutral-800/80">
            
            {/* Left Column: Brand & Socials (5 cols on desktop) */}
            <div className="lg:col-span-5 flex flex-col justify-between">
              <div>
                <h3 className="text-xl font-bold tracking-tight text-white mb-0.5">
                  Cloud ops LLM
                </h3>
                <p className="text-xs text-neutral-400 font-medium mb-4">
                  Cloud Trouble Shooter
                </p>
                <p className="text-sm text-neutral-400 leading-relaxed max-w-sm mb-6">
                  Your intelligent companion for cloud troubleshooting across AWS, Azure, Google Cloud, and Apple Cloud.
                </p>
              </div>

              {/* Social Media Icons */}
              <div className="flex items-center gap-4 text-neutral-400">
                <button
                  onClick={() => openModal('LinkedIn Community', 'Join our CloudOps LinkedIn professional network of 12,000+ SRE and DevOps engineers for weekly outage post-mortems and AI troubleshooting insights.')}
                  className="hover:text-white transition-colors cursor-pointer p-1"
                  aria-label="LinkedIn"
                >
                  <LinkedInIcon className="w-5 h-5" />
                </button>
                <button
                  onClick={() => openModal('GitHub Repository', 'Access open-source CloudOps runbooks, CLI diagnostic tools, and RAG connector schemas on our GitHub organization.', [{ label: 'View Dashboard Docs', to: '/dashboard' }])}
                  className="hover:text-white transition-colors cursor-pointer p-1"
                  aria-label="GitHub"
                >
                  <GithubIcon className="w-5 h-5" />
                </button>
                <button
                  onClick={() => openModal('Twitter / X Updates', 'Follow @CloudOpsLLM for real-time major cloud outage alerts, model capability releases, and cloud reliability tips.')}
                  className="hover:text-white transition-colors cursor-pointer p-1"
                  aria-label="Twitter"
                >
                  <TwitterIcon className="w-5 h-5" />
                </button>
                <button
                  onClick={() => openModal('YouTube Tutorials', 'Watch live walkthroughs of automated AWS VPC diagnostics, Kubernetes crash loop debugging, and multi-cloud incident response.')}
                  className="hover:text-white transition-colors cursor-pointer p-1"
                  aria-label="YouTube"
                >
                  <YoutubeIcon className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Navigation Columns (7 cols on desktop) */}
            <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8">
              
              {/* Product Column */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white mb-4">
                  Product
                </h4>
                <ul className="space-y-3 text-sm text-neutral-400">
                  <li>
                    <button
                      onClick={() => openModal('AI Features', 'Cloud ops LLM includes automated root cause analysis, live log ingestion, multi-cloud resource mapping, and generative step-by-step remediation runbooks.', [{ label: 'Explore Dashboard', to: '/dashboard' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Features
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Use Cases', 'Designed for DevOps, SREs, Cloud Architects, and On-Call teams handling complex multi-cloud incidents, high latency, and security misconfigurations.', [{ label: 'Open Troubleshooter', to: '/troubleshoot' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Use Cases
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Pricing Plans', 'Transparent pay-as-you-scale plans for teams of all sizes. Free tier includes 100 incident analyses per month with full AWS and Azure integration.', [{ label: 'View Billing Details', to: '/billing' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Pricing
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Documentation', 'Comprehensive documentation covering REST API integration, webhook alerting, OpenTelemetry ingestion, and custom LLM prompts.', [{ label: 'Knowledge Base', to: '/knowledge' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Docs
                    </button>
                  </li>
                </ul>
              </div>

              {/* Company Column */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white mb-4">
                  Company
                </h4>
                <ul className="space-y-3 text-sm text-neutral-400">
                  <li>
                    <button
                      onClick={scrollToAbout}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      About
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Engineering Blog', 'Deep dives on RAG architecture for cloud metrics, reducing false alerts with LLM reasoning, and building resilient distributed systems.')}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Blog
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Careers at CloudOps', 'We are hiring distributed systems engineers, ML researchers, and cloud reliability specialists across our remote global team.')}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Careers
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Contact Support', 'Need dedicated enterprise support or custom VPC deployment? Contact our solutions engineering team 24/7.', [{ label: 'Talk to Support Agent', to: '/support-agent' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Contact
                    </button>
                  </li>
                </ul>
              </div>

              {/* Legal Column */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white mb-4">
                  Legal
                </h4>
                <ul className="space-y-3 text-sm text-neutral-400">
                  <li>
                    <button
                      onClick={() => openModal('Privacy Policy', 'We strictly adhere to zero-retention principles for production cloud logs and credentials. Your cloud telemetry is processed securely in-memory and never used to train public foundation models.')}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Privacy Policy
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Terms of Service', 'Enterprise-grade SLA guarantees 99.99% service uptime for real-time alerting and incident response copilots.')}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Terms of Service
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Cookie Policy', 'We only utilize essential session cookies required for authentication and security tokens.')}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Cookie Policy
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => openModal('Support & Helpdesk', 'Enterprise customers receive priority 15-minute response SLA. Community support available 24/7 via the interactive Support Agent.', [{ label: 'Open Support Center', to: '/support-agent' }])}
                      className="hover:text-white transition-colors text-left cursor-pointer"
                    >
                      Support
                    </button>
                  </li>
                </ul>
              </div>

            </div>

          </div>

          {/* Bottom Bar: Copyright */}
          <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-neutral-500 gap-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>All Cloud Troubleshooting Systems Operational</span>
            </div>
            <p>© 2024 Cloud ops LLM. All rights reserved.</p>
          </div>

        </div>
      </footer>

      {/* Helper Modal Dialog for clean placeholder navigation */}
      <InfoModal
        isOpen={modalState.isOpen}
        onClose={closeModal}
        title={modalState.title}
        content={modalState.content}
        links={modalState.links}
      />

    </div>
  );
}

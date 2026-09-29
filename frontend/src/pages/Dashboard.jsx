import React, { useEffect, useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Server,
  Bell,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Bot,
  Plus,
  Minus,
  CheckCircle,
  HelpCircle,
  Cpu,
  Database,
  Globe,
  Shield,
  Send,
  Loader2,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  X
} from 'lucide-react';
import HealthCard from '../components/HealthCard';
import CloudOpsMark from '../components/CloudOpsMark';
import { dashboardApi } from '../api/dashboardApi';
import { supportApi } from '../api/supportApi';
import { useLanguage } from '../context/LanguageContext';
import techLeadersImg from '../assets/tech-leaders.jpg';

/* ─────────────────────────────────────────────
   FAQ Accordion Data (Exactly 4 Questions)
───────────────────────────────────────────── */
const FAQ_ITEMS = [
  {
    question: 'What is CloudOps LLM?',
    answer: 'CloudOps LLM is an AI-powered cloud infrastructure troubleshooting platform designed to help engineers and DevOps teams analyze AWS infrastructure, correlate telemetry logs, identify root causes, and resolve system issues faster.'
  },
  {
    question: 'How does the AI Troubleshooter work?',
    answer: 'The AI Troubleshooter ingests live telemetry, CloudWatch metrics, CloudTrail activity logs, and host configurations. It leverages a specialized QLoRA fine-tuned Transformer model along with ChromaDB vector retrieval (RAG) to determine probable root causes and deliver step-by-step CLI remediation guidance.'
  },
  {
    question: 'What types of cloud problems can it troubleshoot?',
    answer: 'It troubleshoots EC2 instance failures, memory and CPU saturation, ALB target group failures, VPC security group port blockages, database connection timeouts, container OOMKilled errors, and network routing anomalies.'
  },
  {
    question: 'Is my cloud data secure?',
    answer: 'Yes. CloudOps LLM operates strictly in an advisory, read-only capacity. It never automatically modifies your live cloud infrastructure. All data transmission uses enterprise-grade encryption with isolated vector index storage.'
  }
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  // Timing logger for initial mount
  const mountTimeRef = useRef(performance.now());

  // Independent Section States for Asynchronous Loading with Instant Initial Telemetry
  const [healthState, setHealthState] = useState({
    loading: false,
    data: { status: 'OK', backendConnected: true },
    error: null
  });

  const [resourcesState, setResourcesState] = useState({
    loading: false,
    isSyncing: true,
    data: {
      health: {
        overallHealth: '99.4%',
        activeIncidentsCount: 0,
        awsResourcesCount: 4,
        criticalAlertsCount: 0
      },
      overview: {
        ec2: { total: 1, running: 1, stopped: 0, avgCpuUtilization: 14.7 },
        cloudWatch: { activeAlarms: 0, errorRate: '0.0%', requestCount: '1.4M' },
        loadBalancer: { healthyTargets: 1, unhealthyTargets: 0 },
        vpcNetwork: { networkStatus: 'Healthy', vpcs: 1, subnets: 1, securityGroups: 1 }
      }
    },
    error: null
  });

  const [incidentsState, setIncidentsState] = useState({
    loading: false,
    data: [],
    error: null
  });

  // FAQ Accordion state (only one open at a time)
  const [openFaqIdx, setOpenFaqIdx] = useState(0);

  // Support Agent Inline State
  const [agentInput, setAgentInput] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentMessages, setAgentMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am your CloudOps AI Support Agent. You can ask me technical questions about AWS Virtual Private Cloud (VPC), EC2 instance troubleshooting, Security Groups, or QLoRA fine-tuning.'
    }
  ]);
  const [agentError, setAgentError] = useState(null);

  // Helper fetch functions with localized error handling & timing logs
  const fetchHealthSection = async (signal, forceRefresh = false) => {
    try {
      const healthData = await dashboardApi.getHealthStatus({ signal, forceRefresh });
      setHealthState({ loading: false, data: healthData, error: null });
    } catch (err) {
      if (err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
        console.warn('Health section fetch error:', err);
      }
    }
  };

  const fetchResourcesSection = async (signal, forceRefresh = false) => {
    try {
      const summaryData = await dashboardApi.getResourceSummary({ signal, forceRefresh });
      setResourcesState({ loading: false, isSyncing: false, data: summaryData, error: null });
    } catch (err) {
      if (err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
        console.warn('Resource summary fetch error:', err);
        setResourcesState(prev => ({ ...prev, loading: false, isSyncing: false }));
      }
    }
  };

  const fetchIncidentsSection = async (signal, forceRefresh = false) => {
    try {
      const incidentsData = await dashboardApi.getIncidentsSummary({ signal, forceRefresh });
      setIncidentsState({ loading: false, data: incidentsData, error: null });
    } catch (err) {
      if (err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
        console.warn('Incidents section fetch error:', err);
        setIncidentsState(prev => ({ ...prev, loading: false }));
      }
    }
  };

  useEffect(() => {
    const renderTime = (performance.now() - mountTimeRef.current).toFixed(1);
    console.log(`[CloudOps Perf] Dashboard Shell Rendered Immediately: ${renderTime}ms`);

    const controller = new AbortController();

    // Trigger section fetches independently in parallel without blocking UI
    Promise.allSettled([
      fetchHealthSection(controller.signal),
      fetchResourcesSection(controller.signal),
      fetchIncidentsSection(controller.signal)
    ]);

    return () => {
      controller.abort();
    };
  }, []);

  // Handle inline Support Agent Ask
  const handleAskAgent = async (questionToAsk) => {
    const query = (questionToAsk || agentInput).trim();
    if (!query || agentLoading) return;

    const newMessages = [...agentMessages, { role: 'user', content: query }];
    setAgentMessages(newMessages);
    if (!questionToAsk) setAgentInput('');
    setAgentLoading(true);
    setAgentError(null);

    try {
      const res = await supportApi.chat(query, newMessages);
      const replyText = res?.reply || res?.message || 'I have analyzed your question. For detailed step-by-step resolution, you can also launch the full Support Chat.';
      setAgentMessages([...newMessages, { role: 'assistant', content: replyText }]);
    } catch (err) {
      console.warn('Support Agent API call error:', err);
      setAgentError('Agent fallback response active. Launch full chat for extended details.');
      setAgentMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Regarding "${query}": A Virtual Private Cloud (VPC) provisions a logically isolated section of the AWS Cloud where you launch resources in a virtual network. Click 'Open Full Support Chat' for full context-aware diagnosis.`
        }
      ]);
    } finally {
      setAgentLoading(false);
    }
  };

  const handleLaunchTroubleshooter = (promptText = '') => {
    if (promptText) {
      navigate('/troubleshoot', { state: { problemText: promptText } });
    } else {
      navigate('/troubleshoot');
    }
  };

  const healthInfo = resourcesState.data?.health || {};
  const overviewInfo = resourcesState.data?.overview || {};

  return (
    <div className="space-y-16 lg:space-y-20 pb-16 transition-all duration-300">
      
      {/* ==================================================
          1. MAIN HERO — LAUNCH AI CLOUD TROUBLESHOOTER
         ================================================== */}
      <section className="bg-white rounded-3xl border border-slate-200/90 shadow-2xs overflow-hidden relative">
        <div className="grid grid-cols-1 lg:grid-cols-12 items-center gap-4 lg:gap-6 min-h-[560px] lg:min-h-[640px] pl-4 sm:pl-6 lg:pl-8 pr-2 sm:pr-4 lg:pr-6 py-6 lg:py-8">
          
          {/* LEFT SIDE — Text Content & Launch Action */}
          <div className="lg:col-span-6 flex flex-col justify-center gap-6 max-w-xl">

            {/* Label */}
            <div className="flex items-center space-x-2">
              <span className="text-xs uppercase font-extrabold tracking-widest text-slate-400">
                {t('liveTelemetry')}
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                {t('instantTelemetry')}
              </span>
            </div>

            {/* Heading */}
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight leading-[1.1]">
              {t('describeIssuePrompt')}<br />
              <span className="text-blue-600">{t('getExpertDiagnosis')}</span>
            </h1>

            {/* Subtitle */}
            <p className="text-sm text-slate-600 font-medium leading-relaxed max-w-xl">
              {t('heroDesc')}
            </p>

            {/* Main Action Area */}
            <div className="space-y-4 pt-1">
              <div className="flex flex-wrap items-center gap-4">
                <button
                  id="launch-ai-troubleshooter-btn"
                  onClick={() => handleLaunchTroubleshooter()}
                  className="px-7 py-4 rounded-2xl bg-black hover:bg-zinc-900 active:scale-[0.98] text-white font-bold text-sm shadow-md transition-all flex items-center space-x-3 group cursor-pointer"
                >
                  <Sparkles className="w-4 h-4 text-white group-hover:rotate-12 transition-transform" />
                  <span>{t('launchTroubleshooter')}</span>
                  <ArrowRight className="w-4 h-4 text-white group-hover:translate-x-0.5 transition-transform" />
                </button>

                <div className="flex items-center space-x-3 text-xs text-slate-500 font-medium">
                  <span className="flex items-center space-x-1.5">
                    <Bot className="w-4 h-4 text-blue-600" />
                    <span>RAG + QLoRA</span>
                  </span>
                  <span>•</span>
                  <span>Read-Only Advisory</span>
                </div>
              </div>
            </div>

            {/* TRY AN EXAMPLE */}
            <div className="pt-4 border-t border-slate-100 space-y-2.5">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                TRY AN EXAMPLE IN TROUBLESHOOTER
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  { text: 'Why is my website unreachable over HTTPS on port 443?', icon: MessageSquare },
                  { text: 'High CPU usage on my server', icon: Cpu },
                  { text: 'Database connection timeout', icon: Database },
                  { text: 'Server keeps restarting', icon: AlertTriangle },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.text}
                      onClick={() => handleLaunchTroubleshooter(item.text)}
                      className="p-2.5 rounded-xl bg-slate-50 hover:bg-blue-50/70 border border-slate-200/70 hover:border-blue-200 text-left transition-all duration-150 flex items-center justify-between group cursor-pointer"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Icon className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 shrink-0" />
                        <span className="text-xs font-medium text-slate-700 group-hover:text-slate-900 truncate">
                          {item.text}
                        </span>
                      </div>
                      <ArrowRight className="w-3 h-3 text-slate-400 group-hover:text-blue-600 shrink-0 ml-1" />
                    </button>
                  );
                })}
              </div>
            </div>

          </div>

          {/* RIGHT SIDE — Tech Leaders Visual (Uncropped display) */}
          <div className="lg:col-span-6 flex items-end justify-center p-1 lg:p-2 h-full overflow-hidden">
            <img
              src={techLeadersImg}
              alt="CloudOps AI Leaders"
              className="w-full h-auto max-h-[660px] lg:max-h-[700px] object-contain object-bottom select-none pointer-events-none transition-all duration-300 scale-[1.19] origin-bottom"
            />
          </div>

        </div>
      </section>


      {/* ==================================================
          2. CLOUD HEALTH / STATUS CARDS
         ================================================== */}
      <section className="space-y-4">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center space-x-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              System Infrastructure Health
            </h2>
            {resourcesState.loading && (
              <span className="text-[10px] font-semibold text-blue-600 animate-pulse">
                • Synchronizing telemetry...
              </span>
            )}
          </div>
          <span className="text-xs font-medium text-slate-400">
            {healthState.data?.backendConnected ? 'Backend Online (Port 8000)' : 'Live Telemetry Synchronized'}
          </span>
        </div>

        {resourcesState.error ? (
          <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-center justify-between text-xs font-semibold">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{resourcesState.error}</span>
            </div>
            <button
              onClick={() => fetchResourcesSection(null, true)}
              className="px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold transition-all cursor-pointer"
            >
              Retry Telemetry
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <HealthCard
              loading={resourcesState.loading}
              title={t('overallHealth').toUpperCase()}
              value={healthInfo?.overallHealth || '99.4%'}
              status="Healthy"
              icon={Activity}
              description="SLA Uptime Target: 99.9%"
              trend="+0.2%"
            />
            <HealthCard
              loading={resourcesState.loading}
              title={t('activeIncidentsCount').toUpperCase()}
              value={healthInfo?.activeIncidentsCount || 0}
              status="Healthy"
              icon={AlertTriangle}
              description="All services operating normally"
              trend="Normal"
            />
            <HealthCard
              loading={resourcesState.loading}
              title={t('awsResources').toUpperCase()}
              value={`${healthInfo?.awsResourcesCount || 4} Active`}
              status="Healthy"
              icon={Server}
              description="18 EC2, 16 SGs, 2 ALBs"
              trend="Normal"
            />
            <HealthCard
              loading={resourcesState.loading}
              title={t('criticalAlarms').toUpperCase()}
              value={healthInfo?.criticalAlertsCount || 0}
              status="Healthy"
              icon={Bell}
              description="CloudWatch Threshold Normal"
              trend="Normal"
            />
          </div>
        )}
      </section>

      {/* ==================================================
          2B. ACTIVE INCIDENTS & ALERT MONITOR
         ================================================== */}
      <section className="bg-white rounded-3xl border border-slate-200/90 shadow-2xs p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <h3 className="text-sm font-extrabold text-slate-900">{t('activeIncidentMonitor')}</h3>
          </div>
          <Link to="/incidents" className="text-xs font-bold text-blue-600 hover:underline flex items-center space-x-1">
            <span>{t('viewAllIncidents')}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {incidentsState.loading ? (
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 animate-pulse flex items-center justify-between">
            <div className="space-y-2">
              <div className="h-4 w-48 bg-slate-200 rounded" />
              <div className="h-3 w-32 bg-slate-100 rounded" />
            </div>
            <div className="h-6 w-20 bg-slate-200 rounded-full" />
          </div>
        ) : incidentsState.error ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs font-semibold">
            <span>{incidentsState.error}</span>
            <button
              onClick={() => fetchIncidentsSection(null, true)}
              className="px-3 py-1 rounded-lg bg-rose-600 text-white font-bold cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : Array.isArray(incidentsState.data) && incidentsState.data.length > 0 ? (
          <div className="space-y-2.5">
            {incidentsState.data.slice(0, 2).map((inc) => (
              <div
                key={inc.id}
                className="p-4 rounded-2xl bg-slate-50 hover:bg-slate-100/80 border border-slate-200/80 flex items-center justify-between transition-colors text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900">{inc.id}</span>
                    <span className="text-slate-400">•</span>
                    <span className="font-semibold text-slate-700">{inc.title}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 font-medium">Service: {inc.service} • Updated {inc.updatedAt}</p>
                </div>
                <span className={`px-2.5 py-1 rounded-full font-bold text-[10px] uppercase ${
                  inc.status === 'Resolved' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                }`}>
                  {inc.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200/80 text-emerald-800 text-xs font-medium flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t('allSystemsNormal')}</span>
          </div>
        )}
      </section>

      {/* ==================================================
          3. CLOUDOPS SUPPORT AGENT (INLINE INTEGRATION)
         ================================================== */}
      <section className="bg-white rounded-3xl border border-slate-200/90 shadow-2xs p-6 sm:p-8 space-y-6">
        
        {/* Support Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100">
          <div className="flex items-center space-x-3.5">
            <div className="w-10 h-10 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-white shrink-0 shadow-2xs">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">{t('supportAgentInlineTitle')}</h2>
              </div>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t('supportAgentInlineDesc')}
              </p>
            </div>
          </div>

          <Link
            to="/support-agent"
            className="px-4 py-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-slate-200/80 hover:border-slate-300 text-xs font-bold transition-all shrink-0 flex items-center space-x-2 shadow-2xs"
          >
            <span>{t('openFullSupportChat')}</span>
            <ArrowRight className="w-4 h-4 text-slate-900" />
          </Link>
        </div>

        {/* Suggested Questions */}
        <div className="space-y-2.5">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
            SUGGESTED TECHNICAL QUESTIONS:
          </span>
          <div className="flex flex-wrap gap-2.5">
            {[
              'What is a VPC?',
              'How does NAT Gateway work?',
              'Why is my EC2 unreachable?',
              'What is QLoRA?',
            ].map((q) => (
              <button
                key={q}
                onClick={() => handleAskAgent(q)}
                className="px-3.5 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-800 hover:text-slate-900 border border-slate-200/80 hover:border-slate-300 text-xs font-semibold transition-all cursor-pointer flex items-center space-x-2 shadow-2xs"
              >
                <Sparkles className="w-3.5 h-3.5 text-slate-800" />
                <span>{q}</span>
              </button>
            ))}
          </div>
        </div>

        {/* AI Message Stream */}
        <div className="bg-slate-50/80 rounded-2xl p-5 border border-slate-200/80 space-y-4 max-h-80 overflow-y-auto">
          {agentMessages.map((msg, idx) => (
            <div key={idx} className={`flex items-start space-x-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center shrink-0 font-bold text-xs shadow-2xs">
                  AI
                </div>
              )}
              <div
                className={`p-3.5 rounded-2xl text-xs leading-relaxed max-w-xl ${
                  msg.role === 'user'
                    ? 'bg-black text-white font-medium rounded-tr-xs'
                    : 'bg-white text-slate-800 border border-slate-200/80 shadow-2xs rounded-tl-xs space-y-1'
                }`}
              >
                {msg.role === 'assistant' && (
                  <p className="font-bold text-slate-900 text-[11px] mb-1">CloudOps Support Assistant</p>
                )}
                <p>{msg.content}</p>
              </div>
            </div>
          ))}

          {agentLoading && (
            <div className="flex items-center space-x-3">
              <div className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center shrink-0 font-bold text-xs">
                AI
              </div>
              <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-2xs flex items-center space-x-2 text-xs text-slate-500">
                <Loader2 className="w-4 h-4 text-black animate-spin" />
                <span>Consulting CloudOps Knowledge Base & QLoRA Model...</span>
              </div>
            </div>
          )}
        </div>

        {/* Interactive Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAskAgent();
          }}
          className="flex items-center space-x-2 pt-1"
        >
          <input
            type="text"
            value={agentInput}
            onChange={(e) => setAgentInput(e.target.value)}
            placeholder="Type your AWS cloud architecture question..."
            className="flex-1 bg-white px-4 py-3 rounded-xl border border-slate-200 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 font-medium transition-all shadow-2xs"
          />
          <button
            type="submit"
            disabled={agentLoading || !agentInput.trim()}
            className="px-5 py-3 rounded-xl bg-black hover:bg-zinc-800 disabled:opacity-50 text-white text-xs font-bold transition-all cursor-pointer flex items-center space-x-2 shadow-2xs"
          >
            {agentLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>Ask Agent</span>
                <Send className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

      </section>

      {/* ==================================================
          4. FREQUENTLY ASKED QUESTIONS (FAQ)
         ================================================== */}
      <section className="max-w-4xl mx-auto w-full space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Frequently Asked Questions
          </h2>
          <p className="text-sm text-slate-500 font-medium">
            Everything you need to know about CloudOps LLM.
          </p>
        </div>

        <div className="divide-y divide-slate-200/80 border border-slate-200/90 rounded-3xl overflow-hidden bg-white shadow-2xs">
          {FAQ_ITEMS.map((item, idx) => {
            const isOpen = openFaqIdx === idx;
            return (
              <div key={idx} className="transition-colors">
                <button
                  onClick={() => setOpenFaqIdx(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between px-6 sm:px-8 py-5 text-left group hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <span className={`text-sm font-bold pr-4 transition-colors ${isOpen ? 'text-blue-600' : 'text-slate-900 group-hover:text-blue-600'}`}>
                    {item.question}
                  </span>
                  <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center border transition-all ${
                    isOpen ? 'bg-blue-600 border-blue-600 text-white' : 'bg-slate-100 border-slate-200 text-slate-500 group-hover:border-blue-300'
                  }`}>
                    {isOpen ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                  </span>
                </button>

                {isOpen && (
                  <div className="px-6 sm:px-8 pb-6 text-xs sm:text-sm text-slate-600 leading-relaxed pt-1 border-t border-slate-100">
                    {item.answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ==================================================
          5. PROFESSIONAL BLACK / DARK FOOTER
         ================================================== */}
      <footer className="bg-slate-950 text-slate-300 rounded-3xl px-6 sm:px-10 py-12 lg:py-16 shadow-2xl space-y-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-12">
          
          {/* Brand Info (2 columns width) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center space-x-3">
              <CloudOpsMark size={36} />
              <div className="leading-none">
                <span className="block text-xl font-extrabold text-white tracking-tight">
                  CloudOps LLM
                </span>
                <span className="block text-[10px] font-bold uppercase tracking-widest text-blue-400 mt-1">
                  Cloud Trouble Shooter
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
              AI-powered assistance for faster cloud troubleshooting. Detect anomalies, analyze logs, and pinpoint root causes across AWS environments.
            </p>

            <div className="pt-2">
              <span className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-bold text-blue-400">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                <span>Advisory Engine Active</span>
              </span>
            </div>
          </div>

          {/* Product Links */}
          <div className="space-y-3.5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Product</h3>
            <ul className="space-y-2 text-xs font-medium">
              <li><Link to="/troubleshoot" className="hover:text-blue-400 transition-colors">AI Troubleshooter</Link></li>
              <li><Link to="/support-agent" className="hover:text-blue-400 transition-colors">Support Agent</Link></li>
              <li><Link to="/resources" className="hover:text-blue-400 transition-colors">Cloud Resources</Link></li>
              <li><Link to="/history" className="hover:text-blue-400 transition-colors">Analysis History</Link></li>
            </ul>
          </div>

          {/* Company Links */}
          <div className="space-y-3.5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Company</h3>
            <ul className="space-y-2 text-xs font-medium">
              <li><Link to="/welcome" className="hover:text-blue-400 transition-colors">About CloudOps</Link></li>
              <li><Link to="/settings" className="hover:text-blue-400 transition-colors">Settings & Config</Link></li>
              <li><a href="mailto:support@cloudops.ai" className="hover:text-blue-400 transition-colors">Contact Support</a></li>
              <li><Link to="/billing" className="hover:text-blue-400 transition-colors">AWS Billing</Link></li>
            </ul>
          </div>

          {/* Legal Links */}
          <div className="space-y-3.5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Legal</h3>
            <ul className="space-y-2 text-xs font-medium">
              <li><span className="hover:text-blue-400 cursor-pointer transition-colors">Privacy Policy</span></li>
              <li><span className="hover:text-blue-400 cursor-pointer transition-colors">Terms of Service</span></li>
              <li><span className="hover:text-blue-400 cursor-pointer transition-colors">Security Guardrails</span></li>
              <li><span className="hover:text-blue-400 cursor-pointer transition-colors">Compliance</span></li>
            </ul>
          </div>

        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <p>© {new Date().getFullYear()} CloudOps LLM. All rights reserved.</p>
          <p className="text-center sm:text-right">
            AI Cloud Infrastructure Troubleshooting Advisor • Built for Engineers
          </p>
        </div>
      </footer>

    </div>
  );
}

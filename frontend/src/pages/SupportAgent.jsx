import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Bot,
  User,
  Send,
  Trash2,
  Sparkles,
  BookOpen,
  Server,
  Cpu,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Zap
} from 'lucide-react';
import { supportApi } from '../api/supportApi';
import CloudOpsMark from '../components/CloudOpsMark';

const STARTER_QUESTIONS = [
  "How does the CloudOps AI Troubleshooter work?",
  "How do I troubleshoot an EC2 website that is unreachable?",
  "What is the difference between CloudWatch and CloudTrail?",
  "How does RAG work in CloudOps?",
  "Why did we choose Qwen2.5-3B?",
  "What is QLoRA?",
  "What does the confidence score mean?"
];

export default function SupportAgent() {
  const location = useLocation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isRemediationMode, setIsRemediationMode] = useState(false);
  const messagesEndRef = useRef(null);
  const rcaAutoTriggered = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Auto-trigger guided remediation if RCA context arrived from Troubleshooter
  useEffect(() => {
    const { rcaContext, autoMessage } = location.state || {};
    if (rcaContext && !rcaAutoTriggered.current) {
      rcaAutoTriggered.current = true;
      setIsRemediationMode(true);
      handleSendWithRca(autoMessage || 'Show me guided remediation steps', rcaContext);
    }
  }, [location.state]);

  // Send with optional rcaContext for guided remediation mode
  const handleSendWithRca = async (text, rcaContext) => {
    const queryText = (text || '').trim();
    if (!queryText) return;

    setError(null);
    const userId = Date.now() + '-rca-user';
    const userMessage = {
      id: userId,
      role: 'user',
      content: queryText,
      isRemediation: true,
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const res = await supportApi.chat(queryText, [], rcaContext);
      const assistantAnswer = res.answer || res.reply || 'No remediation response generated.';
      const assistantId = Date.now() + '-rca-assistant';
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: assistantAnswer,
          sources: res.sources || [],
          provider: res.provider || 'local_guided_remediation',
          isRemediation: true,
        }
      ]);
    } catch (err) {
      console.warn('RCA remediation request error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (textToSend) => {
    const queryText = (textToSend || input).trim();
    if (!queryText || loading) return;

    setError(null);
    const userId = Date.now() + '-' + Math.random().toString(36).substring(2, 7) + '-user';
    const userMessage = { id: userId, role: 'user', content: queryText };

    // Capture PREVIOUS history before appending current user message
    const previousHistory = messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content
    }));

    setMessages((prev) => [...prev, userMessage]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const res = await supportApi.chat(queryText, previousHistory);
      
      const assistantAnswer = res.answer || res.reply || 'No response generated.';
      
      // Deduplicate sources by title and filter low relevance (<0.35)
      const rawSources = res.sources || [];
      const seenTitles = new Set();
      const uniqueSources = [];
      for (const s of rawSources) {
        const titleKey = (s.title || '').trim().toLowerCase();
        const score = s.relevance !== undefined ? s.relevance : (s.score !== undefined ? s.score : 0);
        if (titleKey && !seenTitles.has(titleKey) && score >= 0.35 && uniqueSources.length < 3) {
          seenTitles.add(titleKey);
          uniqueSources.push({
            title: s.title,
            category: s.category || 'general',
            relevancePercent: Math.round(score * 100)
          });
        }
      }

      const assistantId = Date.now() + '-' + Math.random().toString(36).substring(2, 7) + '-assistant';
      const assistantMessage = {
        id: assistantId,
        role: 'assistant',
        content: assistantAnswer,
        sources: uniqueSources,
        provider: res.provider || 'local_qlora',
        fallback_used: !!res.fallback_used
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.warn('Support Agent chat request error:', err);
      setError('Failed to reach Support Agent API. Please verify that backend server is running on http://localhost:8000.');
      const errorId = Date.now() + '-' + Math.random().toString(36).substring(2, 7) + '-error';
      const errorMessage = {
        id: errorId,
        role: 'assistant',
        content: "### Service Temporarily Unavailable\n\nUnable to communicate with the Support Agent backend service. Please check your connection or verify that the backend server is running.",
        sources: []
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setInput('');
    setError(null);
  };

  const formatBoldText = (str) => {
    const parts = str.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-[#0F172A]">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  const renderMarkdownText = (text) => {
    if (!text) return null;
    const lines = text.split('\n');

    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return <h3 key={idx} className="text-sm font-bold text-[#0F172A] mt-3 mb-1.5">{line.replace('### ', '')}</h3>;
      }
      if (line.startsWith('## ')) {
        return <h2 key={idx} className="text-base font-bold text-[#0F172A] mt-4 mb-2">{line.replace('## ', '')}</h2>;
      }
      if (line.startsWith('# ')) {
        return <h1 key={idx} className="text-lg font-bold text-[#0F172A] mt-4 mb-2">{line.replace('# ', '')}</h1>;
      }
      // Table row rendering
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const cells = line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim());
        if (cells.some(c => c.includes('---'))) return null; // Skip header divider
        return (
          <div key={idx} className="grid grid-cols-3 gap-2 p-2 bg-[#F0F7FF] rounded-lg my-1 text-xs font-mono text-[#0F172A]">
            {cells.map((cell, cIdx) => (
              <span key={cIdx} className="truncate">{formatBoldText(cell)}</span>
            ))}
          </div>
        );
      }
      // Bullet points
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        const bulletContent = line.trim().substring(2);
        return (
          <li key={idx} className="ml-4 list-disc text-xs text-[#334155] my-1 leading-relaxed">
            {formatBoldText(bulletContent)}
          </li>
        );
      }
      // Numbered lists
      if (/^\d+\.\s/.test(line.trim())) {
        const numContent = line.trim().replace(/^\d+\.\s/, '');
        return (
          <li key={idx} className="ml-4 list-decimal text-xs text-[#334155] my-1 leading-relaxed">
            {formatBoldText(numContent)}
          </li>
        );
      }
      if (line.startsWith('```')) {
        return null;
      }
      if (!line.trim()) {
        return <div key={idx} className="h-1.5" />;
      }
      return (
        <p key={idx} className="text-xs text-[#334155] leading-relaxed my-1">
          {formatBoldText(line)}
        </p>
      );
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-6xl mx-auto pb-8">
      {/* PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
              CloudOps Support Agent
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] font-normal">
            Your AI technical assistant for CloudOps, AWS infrastructure, and our AI/LLM system.
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <button
            onClick={handleClear}
            className="px-3.5 py-2 rounded-xl border border-[#E2E8F0] bg-white text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] text-xs font-semibold transition-all flex items-center space-x-2 shadow-2xs cursor-pointer"
            title="Clear Conversation"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-500" />
            <span>Clear Conversation</span>
          </button>
        </div>
      </div>

      {/* CHAT CONTAINER */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-2xs overflow-hidden flex flex-col h-[620px]">

        {/* REMEDIATION MODE BANNER */}
        {isRemediationMode && (
          <div className="px-4 py-2.5 bg-blue-600 flex items-center space-x-2.5 shrink-0">
            <Zap className="w-4 h-4 text-blue-200 shrink-0" />
            <span className="text-xs font-bold text-white">
              Guided Remediation Mode — AI Support is providing step-by-step CHECK / FIX / VERIFY instructions from your RCA diagnosis.
            </span>
            <button
              onClick={() => setIsRemediationMode(false)}
              className="ml-auto text-blue-200 hover:text-white text-[10px] font-semibold shrink-0 underline"
            >
              Exit
            </button>
          </div>
        )}

        {/* CHAT THREAD */}
        <div className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-6 bg-[#F8FAFC]">
          {messages.length === 0 ? (
            /* EMPTY STATE STARTER PROMPTS */
            <div className="h-full flex flex-col justify-center items-center text-center p-6 space-y-6 my-auto">
              <div className="p-3.5 rounded-2xl bg-white border border-slate-200/90 shadow-md flex items-center justify-center">
                <CloudOpsMark size={64} />
              </div>

              <div className="max-w-xl space-y-2">
                <h3 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">Welcome to CloudOps Support Agent</h3>
              </div>

              <div className="w-full max-w-2xl space-y-2 text-left">
                <p className="text-[11px] font-bold text-[#0284C7] uppercase tracking-wider flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Select a Starter Question</span>
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {STARTER_QUESTIONS.map((q, qIdx) => (
                    <button
                      key={qIdx}
                      onClick={() => handleSend(q)}
                      className="p-3 rounded-xl bg-white hover:bg-[#F0F7FF] border border-[#E2E8F0] hover:border-[#BAE6FD] text-[#0F172A] hover:text-[#0284C7] text-xs font-semibold transition-all text-left flex items-start justify-between group cursor-pointer shadow-2xs"
                    >
                      <span className="leading-snug pr-2">{q}</span>
                      <ArrowRight className="w-4 h-4 text-[#0284C7] opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* MESSAGE LIST */
            messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.id || idx}
                  className={`flex gap-3 sm:gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {!isUser && (
                    <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-900 flex items-center justify-center shrink-0 shadow-2xs mt-1 p-1">
                      <CloudOpsMark size={24} />
                    </div>
                  )}

                  <div className={`max-w-3xl space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
                    {/* Bubble */}
                    <div
                      className={`p-4.5 rounded-2xl text-xs shadow-2xs ${
                        isUser
                          ? 'bg-[#0284C7] text-white rounded-br-none font-medium'
                          : 'bg-white border border-[#E2E8F0] text-[#0F172A] rounded-bl-none'
                      }`}
                    >
                      {isUser ? (
                        <p className="text-xs leading-relaxed font-medium whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <div>
                          <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-[#E2E8F0]/60">
                            <span className="text-[11px] font-bold text-[#64748B]">CloudOps Assistant</span>
                            <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-semibold flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                              CloudOps AI
                            </span>
                          </div>
                          <div className="space-y-1.5">{renderMarkdownText(msg.content)}</div>
                        </div>
                      )}
                    </div>

                    {/* Sources Badge List */}
                    {!isUser && msg.sources && msg.sources.length > 0 && msg.provider === 'groq_fallback' && (
                      <div className="pt-2 border-t border-[#E2E8F0]/80 space-y-1.5">
                        <span className="text-[11px] font-bold text-[#64748B] flex items-center space-x-1">
                          <BookOpen className="w-3.5 h-3.5 text-[#0284C7]" />
                          <span>Sources</span>
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.sources.map((src, sIdx) => (
                            <div
                              key={sIdx}
                              className="px-2.5 py-1 rounded-lg bg-[#F0F7FF] border border-[#BAE6FD] text-[#0284C7] text-[11px] font-semibold flex items-center space-x-1.5"
                            >
                              <span className="font-bold text-[#0F172A]">{src.title}</span>
                              {src.relevancePercent !== undefined && (
                                <span className="text-[10px] text-[#0284C7] font-mono font-bold">
                                  — {src.relevancePercent}%
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-9 h-9 rounded-xl bg-[#0F172A] text-white flex items-center justify-center shrink-0 shadow-md mt-1">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })
          )}

          {/* Loading Indicator */}
          {loading && (
            <div className="flex gap-3 sm:gap-4 items-start">
              <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-900 flex items-center justify-center shrink-0 shadow-2xs p-1">
                <CloudOpsMark size={24} className="animate-pulse" />
              </div>
              <div className="p-4 rounded-2xl bg-white border border-[#E2E8F0] rounded-bl-none shadow-2xs flex items-center space-x-3">
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#0284C7] animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-[#0284C7] animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-[#0284C7] animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs text-[#64748B] font-semibold">Support Agent is processing your inquiry...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* INPUT BAR */}
        <div className="p-3 sm:p-4 bg-white border-t border-[#E2E8F0]">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              placeholder="Ask Technical Question About Cloud"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-xl bg-gray-100 border border-gray-300 text-gray-900 placeholder-gray-500 text-xs font-medium focus:outline-none focus:border-black focus:bg-white transition-all shadow-2xs"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="px-6 py-3 rounded-xl bg-black hover:bg-zinc-900 disabled:opacity-50 text-white text-xs font-bold transition-all flex items-center space-x-2 shrink-0 shadow-sm cursor-pointer"
            >
              <span className="text-white font-bold">Send</span>
              <Send className="w-3.5 h-3.5 text-white" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

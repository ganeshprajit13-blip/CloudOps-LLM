import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  BookOpen,
  ArrowRight,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Copy,
  Check,
  Bot,
  Zap
} from 'lucide-react';

export default function AIAnalysis({ data }) {
  const [copied, setCopied] = useState(false);
  const [sentToSupport, setSentToSupport] = useState(false);
  const navigate = useNavigate();

  if (!data) return null;

  const problem = data.problem || 'Cloud Infrastructure Analysis';
  const probableRootCause = data.probable_root_cause || data.probableRootCause || 'Underlying cause undetermined.';
  const recommendation = data.recommendation || data.recommendedAction || 'Review AWS telemetry and configuration.';
  const impact = data.impact || 'Users may experience service degradation or connectivity issues.';

  // Normalize confidence (e.g. 0.91 -> 91, or 91 -> 91)
  const rawConfidence = data.confidence !== undefined && data.confidence !== null ? data.confidence : 0.95;
  const confidenceNum = typeof rawConfidence === 'number'
    ? (rawConfidence <= 1 ? Math.round(rawConfidence * 100) : Math.round(rawConfidence))
    : 90;

  // Deduplicate evidence items
  const rawEvidence = Array.isArray(data.evidence) ? data.evidence : [];
  const uniqueEvidence = Array.from(new Set(rawEvidence.map(item =>
    typeof item === 'string' ? item.trim() : JSON.stringify(item)
  ))).map(str => {
    try {
      return str.startsWith('{') ? JSON.parse(str) : str;
    } catch {
      return str;
    }
  });

  const retrievedKnowledge = Array.isArray(data.retrievedKnowledge || data.retrieved_knowledge)
    ? (data.retrievedKnowledge || data.retrieved_knowledge)
    : [];

  // --- Copy Remediation ---
  const handleCopyCommand = () => {
    if (recommendation) {
      navigator.clipboard.writeText(recommendation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // --- Send to AI Support Agent ---
  const handleSendToSupport = () => {
    setSentToSupport(true);
    const rcaContext = {
      problem,
      incident: problem,
      target_resource_id: data.resource_id || data.target_resource_id || null,
      resource_type: data.resource_type || 'EC2 Instance',
      probable_root_cause: probableRootCause,
      root_cause: probableRootCause,
      recommendation,
      recommended_remediation: recommendation,
      evidence: uniqueEvidence,
      user_impact: impact,
      impact,
      confidence: rawConfidence,
    };

    navigate('/support-agent', {
      state: {
        rcaContext,
        autoMessage: `Guided remediation requested for: ${problem}`,
      }
    });

    setTimeout(() => setSentToSupport(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Confidence Ring */}
      <div className="bg-white p-6 rounded-2xl border border-blue-200 shadow-xs relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 flex-1">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 text-blue-800 border border-blue-200 text-xs font-bold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>AI Cloud Diagnosis</span>
            </div>
            <h2 className="text-xl font-extrabold text-slate-900">{problem}</h2>
            <p className="text-xs text-slate-600 font-medium">Analysis executed via AWS ReadOnly Telemetry + ChromaDB RAG + Qwen LLM</p>
          </div>

          {/* Confidence Ring Display */}
          <div className="flex items-center space-x-4 bg-blue-50/70 p-3.5 rounded-2xl border border-blue-200 shrink-0">
            <div className="relative w-16 h-16 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-blue-100"
                  strokeWidth="3.5"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="text-blue-600 transition-all duration-1000 ease-out"
                  strokeDasharray={`${confidenceNum}, 100`}
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="absolute text-sm font-black text-blue-900">{confidenceNum}%</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">AI Confidence Score</span>
              <span className="text-xs font-extrabold text-blue-800">
                {confidenceNum >= 85 ? 'High Certainty' : confidenceNum >= 60 ? 'Moderate Certainty' : 'Advisory'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Root Cause & Impact */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Probable Root Cause (Span 2) */}
        <div className="md:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-blue-800 font-extrabold text-sm uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-blue-600" />
            <span>Probable Root Cause</span>
          </div>
          <p className="text-sm font-semibold text-slate-900 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-200">
            {probableRootCause}
          </p>
        </div>

        {/* Impact */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 text-slate-800 font-extrabold text-sm uppercase tracking-wider">
            <ShieldAlert className="w-4 h-4 text-blue-600" />
            <span>User Impact</span>
          </div>
          <p className="text-xs font-semibold text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200 leading-relaxed">
            {impact}
          </p>
        </div>
      </div>

      {/* Supporting Evidence Evaluation */}
      {uniqueEvidence.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            <span>Supporting Telemetry &amp; Observable Evidence</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {uniqueEvidence.map((item, idx) => {
              const textContent = typeof item === 'string' ? item : (item.label ? `${item.label}: ${item.value}` : JSON.stringify(item));
              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex items-start space-x-3 text-xs transition-colors"
                >
                  <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  <span className="font-semibold text-slate-800 leading-snug">{textContent}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendation + Dual Action Buttons */}
      <div className="bg-white p-6 rounded-2xl border border-blue-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h3 className="text-sm font-extrabold text-blue-900 uppercase tracking-wider flex items-center space-x-2">
            <ArrowRight className="w-4 h-4 text-blue-600" />
            <span>Recommended Action Step</span>
          </h3>

          {/* Dual action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Copy Remediation */}
            <button
              id="btn-copy-remediation"
              onClick={handleCopyCommand}
              className="px-3 py-1.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-bold transition-colors flex items-center space-x-1.5"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
              <span>{copied ? 'Copied!' : 'Copy Remediation'}</span>
            </button>

            {/* Send to AI Support */}
            <button
              id="btn-send-to-support"
              onClick={handleSendToSupport}
              className="px-3 py-1.5 rounded-xl bg-black hover:bg-zinc-800 active:scale-95 text-white border border-zinc-900 text-xs font-bold transition-all flex items-center space-x-1.5 shadow-sm"
            >
              {sentToSupport
                ? <Check className="w-3.5 h-3.5 text-emerald-300" />
                : <Bot className="w-3.5 h-3.5 text-white" />
              }
              <Zap className="w-3 h-3 text-white/80" />
              <span>{sentToSupport ? 'Opening Support...' : 'Send to AI Support'}</span>
            </button>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-200 font-mono text-xs font-bold text-blue-900 leading-relaxed whitespace-pre-wrap">
          {recommendation}
        </div>

        {/* Safety Disclaimer Callout */}
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-xs flex items-center space-x-3 font-semibold">
          <AlertTriangle className="w-5 h-5 text-blue-600 shrink-0" />
          <span>
            AI provides read-only recommendations. No infrastructure modifications are automatically executed.
            Use <strong>Send to AI Support</strong> for guided step-by-step CHECK / FIX / VERIFY remediation instructions.
          </span>
        </div>
      </div>

      {/* Retrieved Knowledge Base RAG Docs */}
      {retrievedKnowledge.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-blue-600" />
            <span>Retrieved RAG Knowledge References</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {retrievedKnowledge.map((doc, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-50 border border-slate-200 hover:border-blue-300 transition-colors space-y-2"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-extrabold text-slate-900">{doc.title || doc.source || `Reference #${idx + 1}`}</span>
                  {doc.score !== undefined && (
                    <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 text-[10px] font-bold border border-blue-200">
                      Score {typeof doc.score === 'number' ? doc.score.toFixed(2) : doc.score}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed italic">{doc.text || doc.snippet}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                  <span>Source: {doc.service || doc.category || doc.source}</span>
                  <ExternalLink className="w-3 h-3 text-slate-400" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

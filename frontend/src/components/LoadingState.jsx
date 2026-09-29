import React, { useEffect, useState } from 'react';

/* ─── Step definitions ───────────────────────────────────────────────── */
const STEPS = [
  {
    id: 'fastapi',
    title: 'Connecting to FastAPI backend...',
    description: 'Establishing secure connection and authenticating services',
  },
  {
    id: 'cloudwatch',
    title: 'Analyzing infrastructure metrics...',
    description: 'Fetching CloudWatch logs, metrics and events',
  },
  {
    id: 'rag',
    title: 'Retrieving RAG knowledge base context...',
    description: 'Searching relevant documentation and past incidents',
  },
  {
    id: 'llm',
    title: 'Generating LLM root cause diagnosis...',
    description: 'Processing analysis and preparing response',
  },
];

function nowTime() {
  return new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/* ─── Animated SVG progress ring ────────────────────────────────────── */
function ProgressRing({ progress }) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  return (
    <svg width="110" height="110" viewBox="0 0 110 110" style={{ position: 'absolute', inset: 0 }}>
      <circle cx="55" cy="55" r={r} fill="none" stroke="#E2E8F0" strokeWidth="6" />
      <circle
        cx="55" cy="55" r={r} fill="none"
        stroke="#3B82F6" strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - progress)}
        transform="rotate(-90 55 55)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
    </svg>
  );
}

/* ─── Mini spinner ───────────────────────────────────────────────────── */
function MiniSpinner() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" className="animate-spin" style={{ animationDuration: '0.9s' }}>
      <circle cx="12" cy="12" r="10" fill="none" stroke="#BFDBFE" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" fill="none" stroke="#3B82F6" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* ─── Status check SVG ───────────────────────────────────────────────── */
function CheckBadge() {
  return (
    <span style={{
      flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
      background: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </span>
  );
}

/* ─── DB icon (step 3) ───────────────────────────────────────────────── */
function DBBadge({ active }) {
  return (
    <span style={{
      flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
      background: active ? '#DBEAFE' : '#F1F5F9',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke={active ? '#3B82F6' : '#94A3B8'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.657-4.029 3-9 3S3 13.657 3 12" />
        <path d="M3 5v14c0 1.657 4.029 3 9 3s9-1.343 9-3V5" />
      </svg>
    </span>
  );
}

/* ─── Spark icon (step 4) ────────────────────────────────────────────── */
function SparkBadge() {
  return (
    <span style={{
      flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
      background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="#CBD5E1" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z" />
      </svg>
    </span>
  );
}

/* ─── Network icon (step 1) ──────────────────────────────────────────── */
function NetworkBadge() {
  return (
    <span style={{
      flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
      background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="#94A3B8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="6" height="6" rx="1" />
        <rect x="16" y="2" width="6" height="6" rx="1" />
        <rect x="9" y="16" width="6" height="6" rx="1" />
        <line x1="5" y1="8" x2="5" y2="12" />
        <line x1="5" y1="12" x2="12" y2="12" />
        <line x1="19" y1="8" x2="19" y2="12" />
        <line x1="19" y1="12" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12" y2="12" />
      </svg>
    </span>
  );
}

/* ─── CPU icon (step 2) ──────────────────────────────────────────────── */
function CpuBadge() {
  return (
    <span style={{
      flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
      background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="#94A3B8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <rect x="9" y="9" width="6" height="6" />
        <line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" />
        <line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" />
        <line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" />
        <line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
      </svg>
    </span>
  );
}

function getIcon(index, isDone, isCurrent) {
  if (isDone) return <CheckBadge />;
  if (index === 0) return <NetworkBadge />;
  if (index === 1) return <CpuBadge />;
  if (index === 2) return <DBBadge active={isCurrent} />;
  return <SparkBadge />;
}

/* ─── Step card ──────────────────────────────────────────────────────── */
function StepCard({ step, index, currentStep, timestamps }) {
  const isDone = index < currentStep;
  const isCurrent = index === currentStep;
  const isPending = index > currentStep;

  const cardBg = isDone ? '#F0FDF4' : isCurrent ? '#EFF6FF' : '#FAFAFA';
  const cardBorder = isDone ? '#BBF7D0' : isCurrent ? '#93C5FD' : '#E2E8F0';
  const cardShadow = isCurrent ? '0 2px 16px rgba(59,130,246,0.10)' : '0 1px 4px rgba(15,23,42,0.04)';

  const titleColor = isDone ? '#15803D' : isCurrent ? '#1D4ED8' : '#64748B';
  const descColor  = isDone ? '#166534' : isCurrent ? '#3B82F6' : '#94A3B8';

  return (
    <div style={{
      background: cardBg,
      border: `1.5px solid ${cardBorder}`,
      borderRadius: '14px',
      padding: '18px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: '14px',
      boxShadow: cardShadow,
      transition: 'all 0.35s ease',
      opacity: isPending ? 0.8 : 1,
    }}>
      {/* icon */}
      {getIcon(index, isDone, isCurrent)}

      {/* center */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontWeight: 700, fontSize: '13.5px', color: titleColor, marginBottom: 3, lineHeight: 1.35 }}>
          {step.title}
        </p>
        <p style={{ fontSize: '12px', color: descColor, lineHeight: 1.45 }}>
          {step.description}
        </p>
      </div>

      {/* right status */}
      <div style={{ flexShrink: 0, textAlign: 'right', minWidth: '92px' }}>
        {isDone && (
          <>
            <p style={{ fontWeight: 700, fontSize: '13px', color: '#16A34A' }}>Completed</p>
            {timestamps[index] && (
              <p style={{ fontSize: '11px', color: '#6B7280', marginTop: 2 }}>{timestamps[index]}</p>
            )}
          </>
        )}
        {isCurrent && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
            <p style={{ fontWeight: 700, fontSize: '13px', color: '#3B82F6' }}>In Progress</p>
            {timestamps[index] && (
              <p style={{ fontSize: '11px', color: '#6B7280' }}>{timestamps[index]}</p>
            )}
            <MiniSpinner />
          </div>
        )}
        {isPending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, justifyContent: 'flex-end' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#CBD5E1" strokeWidth="2">
              <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
            <p style={{ fontWeight: 600, fontSize: '13px', color: '#94A3B8' }}>Pending</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Main exported AILoadingState ───────────────────────────────────── */
export function AILoadingState({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [timestamps, setTimestamps] = useState({});
  const [ringProgress, setRingProgress] = useState(0.12);

  useEffect(() => {
    setTimestamps(prev => ({ ...prev, [currentStep]: nowTime() }));
    setRingProgress(0.12 + (currentStep / (STEPS.length - 1)) * 0.76);
  }, [currentStep]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev < STEPS.length - 1) return prev + 1;
        clearInterval(timer);
        if (onComplete) onComplete();
        return prev;
      });
    }, 1100);
    return () => clearInterval(timer);
  }, [onComplete]);

  return (
    <div style={{
      background: '#FFFFFF',
      borderRadius: '20px',
      border: '1px solid #E2E8F0',
      boxShadow: '0 4px 32px rgba(15,23,42,0.07)',
      padding: '48px 36px 36px',
      maxWidth: '640px',
      margin: '28px auto',
      fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
    }}>

      {/* ── Robot + progress ring ─────────────────────────────────── */}
      <div style={{ textAlign: 'center', marginBottom: '34px' }}>
        {/* ring container */}
        <div style={{ position: 'relative', width: 110, height: 110, margin: '0 auto 22px' }}>
          <ProgressRing progress={ringProgress} />
          {/* inner white circle */}
          <div style={{
            position: 'absolute', top: 10, left: 10, right: 10, bottom: 10,
            borderRadius: '50%', background: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(59,130,246,0.13)',
          }}>
            {/* Bot icon */}
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
              stroke="#3B82F6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="8" width="18" height="13" rx="3" />
              <path d="M12 8V5" />
              <circle cx="12" cy="4" r="1" />
              <circle cx="8.5" cy="14" r="1.5" fill="#3B82F6" stroke="none" />
              <circle cx="15.5" cy="14" r="1.5" fill="#3B82F6" stroke="none" />
              <path d="M9 18h6" strokeWidth="1.8" />
              <line x1="3" y1="13" x2="1" y2="13" />
              <line x1="21" y1="13" x2="23" y2="13" />
            </svg>
          </div>
        </div>

        <h2 style={{
          fontSize: '26px', fontWeight: 800, color: '#0F172A',
          letterSpacing: '-0.02em', margin: '0 0 8px', lineHeight: 1.2,
        }}>
          AI Infrastructure Troubleshooting Active
        </h2>
        <p style={{ fontSize: '14px', color: '#64748B', fontWeight: 500, margin: 0 }}>
          Executing RAG &amp; CloudWatch diagnostics via FastAPI
        </p>
      </div>

      {/* ── Step cards ─────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '11px' }}>
        {STEPS.map((step, idx) => (
          <StepCard
            key={step.id}
            step={step}
            index={idx}
            currentStep={currentStep}
            timestamps={timestamps}
          />
        ))}
      </div>

      {/* ── Bottom disclaimer ──────────────────────────────────────── */}
      <p style={{
        textAlign: 'center', fontSize: '12px', color: '#94A3B8',
        marginTop: '28px', lineHeight: 1.5,
      }}>
        This may take a few moments. Please don&apos;t close this window.
      </p>
    </div>
  );
}

/* ─── Default export: generic spinner ───────────────────────────────── */
export default function LoadingSpinner({ message = 'Loading AWS infrastructure data...' }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 space-y-4">
      <div className="w-10 h-10 border-4 border-blue-100 border-t-blue-500 rounded-full animate-spin" />
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{message}</p>
    </div>
  );
}

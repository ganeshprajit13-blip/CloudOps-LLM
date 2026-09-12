import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ScenarioDocs, GroundTruth, GroundTruthIncident } from '../types/investigation'
import { fmtDate, humanize, SEV } from '../utils/format'
import { extractDomainTag } from '../utils/domainTags'
import { getRootCause } from './AnswerKey'
import CausationChain from './CausationChain'

interface ScenarioDetailProps {
  scenarioName: string
  docs: ScenarioDocs
  /** Populate the message input with this text */
  onUsePrompt?: (text: string) => void
}

// ---------------------------------------------------------------------------
// HITL flow step labels + normalizer
// ---------------------------------------------------------------------------

const FLOW_KEYS = [
  '1_vague_report',
  '2_clarification',
  '3_user_response',
  '4_focused_investigation',
  '5_correct_root_cause',
] as const

const FLOW_LABELS: Record<string, { num: string; label: string }> = {
  '1_vague_report':         { num: '1', label: 'User reports' },
  '2_clarification':        { num: '2', label: 'Agent asks' },
  '3_user_response':        { num: '3', label: 'User clarifies' },
  '4_focused_investigation': { num: '4', label: 'Agent investigates' },
  '5_correct_root_cause':   { num: '5', label: 'Root cause found' },
}

/**
 * Normalize hitl_flow from any source format into the canonical object format.
 *
 * Handles:
 *  - Canonical object: { "1_vague_report": "...", ... }
 *  - String array:     ["text1", "text2", ...]
 *  - Object array:     [{ step: 1, action: "...", outcome: "..." }, ...]
 */
function normalizeHitlFlow(raw: unknown): Record<string, string> | null {
  if (!raw) return null

  // Array formats: string[] or {step, action, outcome}[]
  if (Array.isArray(raw)) {
    const out: Record<string, string> = {}
    raw.forEach((item: unknown, i: number) => {
      if (i >= FLOW_KEYS.length) return
      const key = FLOW_KEYS[i]
      if (typeof item === 'string') {
        out[key] = item
      } else if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>
        const parts = [obj.action, obj.outcome].filter(Boolean)
        out[key] = parts.length > 0 ? parts.join(' \u2192 ') : JSON.stringify(item)
      }
    })
    return Object.keys(out).length > 0 ? out : null
  }

  // Object format: pass through string values
  if (typeof raw === 'object') {
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (typeof v === 'string') out[k] = v
    }
    return Object.keys(out).length > 0 ? out : null
  }

  return null
}

// ---------------------------------------------------------------------------
// Generate suggested prompts from ground_truth
// ---------------------------------------------------------------------------

interface Prompt {
  label: string
  text: string
}

function buildPrompts(gt: GroundTruth | null): Prompt[] {
  const out: Prompt[] = []

  // Vague opening prompt — triggers HITL clarification questions
  const flow = normalizeHitlFlow(gt?.hitl_flow)
  const vague = flow?.['1_vague_report']
  if (vague) {
    out.push({ label: 'Vague report (triggers clarification)', text: vague })
  }

  if (gt?.incidents) {
    for (const [, inc] of Object.entries(gt.incidents)) {
      const date = inc.date ? fmtDate(inc.date) : ''
      const time = inc.time_range ?? ''
      const sym = inc.symptom ?? ''
      if (date || sym) {
        const text = [
          date && `The incident occurred on ${inc.date}`,
          time && `around ${time}`,
          sym && `\u2014 ${sym}`,
        ]
          .filter(Boolean)
          .join(' ')
        out.push({ label: `${date} ${time}`.trim(), text })
      }
    }
  }

  if (gt?.current_incident?.description) {
    out.push({ label: 'Most likely incident', text: gt.current_incident.description })
  }

  return out
}

// ---------------------------------------------------------------------------
// Collapsible section wrapper
// ---------------------------------------------------------------------------

function Section({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string
  subtitle?: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
      >
        <div>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {title}
          </span>
          {subtitle && (
            <span className="text-xs text-gray-400 ml-2">{subtitle}</span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="border-t border-gray-100">{children}</div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ScenarioDetail({ scenarioName, docs, onUsePrompt }: ScenarioDetailProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const gt = docs.ground_truth
  const prompts = buildPrompts(gt)
  const incidents = gt?.incidents ? Object.entries(gt.incidents) : []
  const domain = extractDomainTag(gt?.domain ?? scenarioName.replace(/-/g, ' '))
  const rc = gt ? getRootCause(gt) : null
  const flow = normalizeHitlFlow(gt?.hitl_flow)
  const redHerrings = gt?.red_herrings ?? []
  const chain = gt?.causation_chain ?? []

  const flowSteps = flow
    ? Object.entries(flow)
        .filter(([key]) => key in FLOW_LABELS)
        .map(([key, val]) => ({ key, val, meta: FLOW_LABELS[key] }))
    : []

  const handleCopy = (text: string, idx: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx)
      setTimeout(() => setCopiedIdx(null), 1500)
    })
  }

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-gray-900">{gt?.display_name || humanize(scenarioName)}</h2>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${domain.bg} ${domain.text}`}>
            {domain.label}
          </span>
          {gt?.domain && gt.domain !== domain.label && (
            <span className="text-xs text-gray-400">{gt.domain}</span>
          )}
          {incidents.length > 1 && (
            <span className="text-xs px-2.5 py-1 rounded-full font-medium border border-gray-300 text-gray-600 bg-white">
              {incidents.length} incidents
            </span>
          )}
        </div>
      </div>

      {/* What Happened (plain English) */}
      {gt?.plain_english_summary && (
        <div className="border border-blue-100 rounded-lg bg-blue-50/50 px-4 py-3">
          <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
            What Happened
          </span>
          <p className="text-sm text-gray-800 leading-relaxed mt-1.5">
            {gt.plain_english_summary}
          </p>
        </div>
      )}

      {/* Suggested prompts — click to load into message input */}
      {prompts.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Start investigating
          </span>
          <p className="text-[11px] text-gray-400 -mt-1">
            Pick a prompt — it loads into the message bar, then press Enter
          </p>
          <div className="space-y-1.5">
            {prompts.map((p, i) => (
              <button
                key={i}
                onClick={() => {
                  if (onUsePrompt) {
                    onUsePrompt(p.text)
                    setCopiedIdx(i)
                    setTimeout(() => setCopiedIdx(null), 1500)
                  } else {
                    handleCopy(p.text, i)
                  }
                }}
                className="w-full flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50
                  hover:border-teal-300 hover:bg-teal-50/50 transition-colors text-left group"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-medium text-gray-400 mb-0.5">
                    {p.label}
                  </div>
                  <div className="text-sm text-gray-700">
                    {p.text}
                  </div>
                </div>
                <span className="flex-none text-xs font-medium text-gray-400 group-hover:text-teal-600 transition-colors">
                  {copiedIdx === i ? (
                    <span className="text-green-600">Loaded</span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      Use this
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* How It Unfolded (Mermaid diagram) */}
      {chain.length > 0 && (
        <div className="border border-gray-200 rounded-lg bg-white px-4 py-3">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            How It Unfolded
          </span>
          <CausationChain chain={chain} />
        </div>
      )}

      {/* Dig Deeper (collapsible sections) */}
      <div className="pt-1">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Dig Deeper
        </span>
      </div>

      {/* Investigation Guide (merged: root cause, red herrings, flow, incident report) */}
      {(rc || gt?.description || docs.incident || redHerrings.length > 0) && (
        <Section title="Investigation Guide" defaultOpen={false}>
          <div className="px-4 pb-4 pt-3 space-y-4">
            {rc && (
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Root Cause Target
                </div>
                <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2.5">
                  {rc.service && (
                    <span className="inline-block text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded font-mono mb-1 border border-green-200">
                      {rc.service}
                    </span>
                  )}
                  {rc.issue && (
                    <div className="text-sm font-medium text-green-900">{rc.issue}</div>
                  )}
                  {rc.details && (
                    <p className="text-xs text-green-800 leading-relaxed mt-1.5">{rc.details}</p>
                  )}
                </div>
              </div>
            )}

            {redHerrings.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Red Herrings
                </div>
                <div className="space-y-1.5">
                  {redHerrings.map((rh, i) => {
                    const text = typeof rh === 'string'
                      ? rh
                      : (rh.name ?? rh.symptom ?? rh.event ?? rh.evidence ?? '')
                    const detail = typeof rh === 'object'
                      ? (rh.why_misleading ?? rh.description ?? undefined)
                      : undefined
                    return (
                      <div key={i} className="flex gap-2 items-baseline">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-none relative top-[1px]" />
                        <div>
                          <span className="text-xs text-gray-600">{text}</span>
                          {detail && (
                            <p className="text-[11px] text-gray-400 mt-0.5">{detail}</p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {flowSteps.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Expected Flow
                </div>
                <div className="space-y-0">
                  {flowSteps.map(({ key, val, meta }) => {
                    const isUser = key === '1_vague_report' || key === '3_user_response'
                    return (
                      <div key={key} className="flex gap-2.5 py-1.5">
                        <div className="flex-none flex flex-col items-center">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                            isUser ? 'bg-teal-100 text-teal-600' : 'bg-gray-100 text-gray-500'
                          }`}>
                            {meta.num}
                          </div>
                          {key !== '5_correct_root_cause' && (
                            <div className="w-px flex-1 bg-gray-200 mt-0.5" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0 pb-1">
                          <div className="text-[10px] font-semibold text-gray-400 uppercase">
                            {meta.label}
                          </div>
                          <div className={`text-xs leading-relaxed mt-0.5 ${
                            key === '5_correct_root_cause' ? 'text-green-700 font-medium' : 'text-gray-600'
                          }`}>
                            {val}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {gt?.why_clarification_matters && (
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  Why Clarification Matters
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">{gt.why_clarification_matters}</p>
              </div>
            )}

            {(gt?.description || docs.incident) && (
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Incident Report
                </div>
                <div className="text-sm text-gray-600 leading-relaxed prose prose-sm max-w-none prose-headings:text-gray-800 prose-strong:text-gray-700 prose-p:text-gray-600 prose-p:my-1.5 prose-headings:my-2 prose-ul:my-1 prose-li:my-0.5 prose-hr:my-3">
                  {gt?.description && (
                    <div className="mb-3">
                      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                        {gt.description.trim()}
                      </p>
                      {gt.current_incident?.most_likely_date && (
                        <p className="text-sm text-gray-700 mt-2">
                          <span className="font-semibold">Most likely date:</span>{' '}
                          {gt.current_incident.most_likely_date}
                        </p>
                      )}
                      {docs.incident && <hr className="my-3 border-gray-200" />}
                    </div>
                  )}
                  {docs.incident && <ReactMarkdown>{docs.incident}</ReactMarkdown>}
                </div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Key Incidents */}
      {incidents.length > 0 && (
        <Section title="Key Incidents" subtitle="Reference these when writing your prompt" defaultOpen={false}>
          <div className="divide-y divide-gray-100">
            {incidents.map(([key, inc]: [string, GroundTruthIncident]) => (
              <div key={key} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                <span className="font-mono text-gray-800 font-semibold flex-none w-24">
                  {inc.date ? fmtDate(inc.date) : '\u2014'}
                </span>
                <span className="text-gray-600 flex-none w-24">
                  {inc.time_range ?? ''}
                </span>
                {inc.severity && (
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded font-semibold flex-none ${SEV[inc.severity] ?? 'bg-gray-100 text-gray-600'}`}
                  >
                    {inc.severity}
                  </span>
                )}
                <span className="text-gray-700 leading-snug">
                  {inc.symptom ?? ''}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

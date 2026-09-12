import { useState } from 'react'
import type { ScenarioDocs, GroundTruthIncident } from '../types/investigation'
import { buildResponseEntries } from './HitlGuidance'
import { fmtDate, SEV } from '../utils/format'

interface Props {
  docs: ScenarioDocs
  onUseResponse: (text: string) => void
}

const CLARIFICATION_TYPE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  time_dependent: { label: 'Time-dependent', bg: 'bg-blue-50', text: 'text-blue-700' },
  scope: { label: 'Scope', bg: 'bg-purple-50', text: 'text-purple-700' },
  change_correlation: { label: 'Change Correlation', bg: 'bg-amber-50', text: 'text-amber-700' },
}

export default function ClarificationContextCard({ docs, onUseResponse }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const gt = docs.ground_truth
  if (!gt) return null

  const incidents = gt.incidents ? Object.entries(gt.incidents) : []
  const responseEntries = buildResponseEntries(gt)
  const clarType = gt.hitl_clarification_type
  const typeStyle = clarType ? CLARIFICATION_TYPE_STYLES[clarType] : null

  // Nothing useful to show
  if (incidents.length === 0 && responseEntries.length === 0) return null

  if (collapsed) {
    return (
      <div className="flex-none border-t border-gray-200 bg-white px-6 py-2">
        <div className="mx-auto max-w-4xl flex items-center justify-between">
          <span className="text-xs text-gray-600 font-medium">Incident context available</span>
          <button
            onClick={() => setCollapsed(false)}
            className="text-xs text-teal-600 hover:text-teal-800 font-medium"
          >
            Show
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-none border-t-2 border-teal-500 bg-white px-6 py-4 max-h-[360px] overflow-y-auto shadow-sm">
      <div className="mx-auto max-w-4xl space-y-3">
        {/* Header with type badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm font-semibold text-gray-900">Quick Reference</span>
            {typeStyle && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${typeStyle.bg} ${typeStyle.text}`}>
                {typeStyle.label}
              </span>
            )}
          </div>
          <button
            onClick={() => setCollapsed(true)}
            className="text-xs text-gray-400 hover:text-gray-600 font-medium"
          >
            Hide
          </button>
        </div>

        {/* Key incidents table */}
        {incidents.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 font-medium mb-1.5">Key dates from this scenario:</div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
              <div className="divide-y divide-gray-200">
                {incidents.map(([key, inc]: [string, GroundTruthIncident]) => (
                  <div key={key} className="flex items-start gap-3 px-3 py-2 text-xs">
                    <span className="font-mono text-gray-800 font-semibold w-24 flex-none">
                      {inc.date ? fmtDate(inc.date) : '\u2014'}
                    </span>
                    <span className="text-gray-600 w-24 flex-none">
                      {inc.time_range ?? ''}
                    </span>
                    {inc.severity && (
                      <span className={`text-xs px-1.5 py-0.5 rounded font-semibold flex-none ${SEV[inc.severity] ?? 'bg-gray-100 text-gray-600'}`}>
                        {inc.severity}
                      </span>
                    )}
                    <span className="text-gray-700 leading-snug">
                      {inc.symptom ?? ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Suggested responses */}
        {responseEntries.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 font-medium mb-1.5">Respond to the agent:</div>
            <div className="space-y-2">
              {responseEntries.map((r) => (
                <button
                  key={r.key}
                  onClick={() => onUseResponse(r.text)}
                  className={`w-full text-left border rounded-lg px-3 py-2.5 hover:border-teal-400 hover:bg-teal-50 transition-colors group ${
                    responseEntries.length === 1
                      ? 'bg-teal-50/50 border-teal-200'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      {responseEntries.length > 1 && (
                        <div className="text-xs font-medium text-teal-600 mb-0.5">{r.label}</div>
                      )}
                      <div className="text-sm text-gray-700 leading-snug group-hover:text-teal-700">
                        &ldquo;{r.text}&rdquo;
                      </div>
                    </div>
                    <span className="text-xs text-teal-500 group-hover:text-teal-600 flex-none mt-0.5 font-medium whitespace-nowrap">
                      Use this
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

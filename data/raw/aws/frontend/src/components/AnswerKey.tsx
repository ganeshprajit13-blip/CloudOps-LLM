import { useState } from 'react'
import type { GroundTruth, GroundTruthIncident } from '../types/investigation'
import { humanizeKey } from './HitlGuidance'

// ---------------------------------------------------------------------------
// Normalizers (reusable across components)
// ---------------------------------------------------------------------------

/** Normalize root_cause across different YAML shapes */
export function getRootCause(gt: GroundTruth): { service?: string; issue?: string; details?: string } | null {
  if (gt.root_cause && typeof gt.root_cause === 'object') {
    return gt.root_cause as { service?: string; issue?: string; details?: string }
  }
  if (gt.root_cause && typeof gt.root_cause === 'string') {
    return { issue: gt.root_cause }
  }
  if (gt.ground_truth?.root_cause) {
    return {
      service: gt.ground_truth.root_cause_service as string | undefined,
      issue: typeof gt.ground_truth.root_cause === 'string' ? gt.ground_truth.root_cause : undefined,
    }
  }
  return null
}

/** Normalize trap across different YAML shapes */
export function getTrap(gt: GroundTruth): { obvious_answer?: string; why_wrong?: string } | null {
  if (gt.trap) return gt.trap
  if (gt.ground_truth?.trap) return gt.ground_truth.trap as { obvious_answer?: string; why_wrong?: string }
  return null
}

/** Normalize chain_of_events */
export function getChainOfEvents(gt: GroundTruth): string[] | null {
  if (gt.chain_of_events?.length) return gt.chain_of_events
  if (gt.ground_truth?.chain_of_events?.length) return gt.ground_truth.chain_of_events
  return null
}

/** Get the "why" text for HITL scenarios */
export function getWhyText(gt: GroundTruth): string | null {
  return gt.why_clarification_matters || gt.why_change_correlation_matters || gt.why_scope_matters || gt.without_clarification || null
}

// ---------------------------------------------------------------------------
// Incident row (reusable)
// ---------------------------------------------------------------------------

const SEV_COLORS: Record<string, string> = {
  P1: 'text-red-600',
  P2: 'text-amber-600',
  P3: 'text-blue-600',
}

export function IncidentRow({ incident }: { incident: GroundTruthIncident }) {
  return (
    <div className="flex items-baseline gap-2 text-[11px] py-0.5">
      {incident.date && (
        <span className="flex-none font-mono text-gray-400 text-[10px] w-12">
          {incident.date.slice(5)}
        </span>
      )}
      {incident.severity && (
        <span className={`flex-none font-bold text-[10px] w-5 ${SEV_COLORS[incident.severity] ?? 'text-gray-500'}`}>
          {incident.severity}
        </span>
      )}
      <span className="text-gray-700 truncate">{incident.root_cause?.issue ?? incident.symptom ?? ''}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AnswerKey({ gt }: { gt: GroundTruth }) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const rc = getRootCause(gt)
  const chain = getChainOfEvents(gt)
  const incidents = gt.incidents

  if (!rc && !incidents && !gt.current_incident) return null

  return (
    <div className="space-y-2.5">
      {gt.current_incident?.correct_root_cause && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          <div className="text-[10px] font-semibold text-green-700 mb-0.5">Correct Answer</div>
          <div className="text-xs text-green-900">{gt.current_incident.correct_root_cause}</div>
        </div>
      )}

      {rc && (
        <div>
          {rc.service && (
            <span className="inline-block text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-mono mb-1 border border-gray-200">
              {rc.service}
            </span>
          )}
          {rc.issue && (
            <div className="text-xs font-medium text-gray-900">{rc.issue}</div>
          )}
          {rc.details && (
            <>
              <button
                onClick={() => setDetailsOpen(!detailsOpen)}
                className="text-[10px] text-teal-600 hover:text-teal-800 mt-1"
              >
                {detailsOpen ? 'Hide details' : 'Show details'}
              </button>
              {detailsOpen && (
                <p className="text-[11px] text-gray-600 leading-relaxed mt-1 whitespace-pre-line">{rc.details}</p>
              )}
            </>
          )}
        </div>
      )}

      {chain && (
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Chain of Events</div>
          <div className="space-y-0.5">
            {chain.map((step, i) => (
              <div key={i} className="flex gap-2 text-[11px]">
                <span className="flex-none text-gray-400 font-mono w-3 text-right">{i + 1}</span>
                <span className="text-gray-700">{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {incidents && Object.keys(incidents).length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
            All Incidents ({Object.keys(incidents).length})
          </div>
          <div className="space-y-1">
            {Object.entries(incidents).map(([key, inc]) => (
              <IncidentRow key={key} incident={inc} />
            ))}
          </div>
        </div>
      )}

      {gt.timeline && (
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Timeline</div>
          <div className="space-y-0.5">
            {Object.entries(gt.timeline).map(([date, desc]) => (
              <div key={date} className="flex gap-2 text-[11px]">
                <span className="flex-none text-gray-400 font-mono text-[10px]">{humanizeKey(date)}</span>
                <span className="text-gray-700">{desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

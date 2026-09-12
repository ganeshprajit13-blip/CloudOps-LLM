import type { GroundTruth } from '../types/investigation'
import CopyButton from './CopyButton'

export function humanizeKey(key: string): string {
  return key
    .replace(/^(if_|\d+_)/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export interface ResponseEntry {
  key: string
  label: string
  text: string
  hint: string | null
  correctCause: string | null
}

/** Build the response entries from hitl_flow for reuse by other components */
export function buildResponseEntries(gt: GroundTruth): ResponseEntry[] {
  const flow = gt.hitl_flow
  if (!flow) return []

  const keys = Object.keys(flow).sort()
  const responsesKey = keys.find((k) => k.includes('example_responses'))
  const pathKey = keys.find((k) => k.includes('investigation_path'))

  if (!responsesKey || typeof flow[responsesKey] !== 'object') {
    // Fallback: single user_response string (simple flow)
    const userRespKey = keys.find((k) => k.includes('user_response'))
    if (userRespKey && typeof flow[userRespKey] === 'string') {
      return [{
        key: 'user_response',
        label: 'Example Response',
        text: String(flow[userRespKey]),
        hint: null,
        correctCause: null,
      }]
    }
    return []
  }

  const responses = flow[responsesKey] as Record<string, string>
  const paths = pathKey ? (flow[pathKey] as Record<string, string>) : {}
  const alts = gt.alternate_scenarios ?? {}

  return Object.entries(responses).map(([key, text]) => {
    const pathMatch = Object.entries(paths).find(([pk]) => {
      const stripped = pk.replace(/^if_/, '')
      return key.startsWith(stripped) || stripped.startsWith(key.split('_')[0])
    })
    const altMatch = Object.entries(alts).find(([ak]) => {
      const stripped = ak.replace(/^if_/, '')
      return key.startsWith(stripped) || stripped.startsWith(key.split('_')[0])
    })

    return {
      key,
      label: humanizeKey(key),
      text,
      hint: pathMatch?.[1] ?? null,
      correctCause: altMatch?.[1]?.correct_root_cause ?? null,
    }
  })
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function HitlGuidance({ gt }: { gt: GroundTruth }) {
  const flow = gt.hitl_flow
  if (!flow) return null

  const keys = Object.keys(flow).sort()
  const responsesKey = keys.find((k) => k.includes('example_responses'))

  if (responsesKey && typeof flow[responsesKey] === 'object') {
    return <HitlGuidanceShapeA gt={gt} flow={flow} keys={keys} />
  }

  return <HitlGuidanceShapeB flow={flow} keys={keys} />
}

// ---------------------------------------------------------------------------
// Shape A: Multiple response options (ground_truth has example_responses array)
// ---------------------------------------------------------------------------

function HitlGuidanceShapeA({
  gt,
  flow,
  keys,
}: {
  gt: GroundTruth
  flow: Record<string, unknown>
  keys: string[]
}) {
  const vagueKey = keys.find((k) => k.includes('vague_report'))

  const vagueReport = vagueKey ? String(flow[vagueKey]) : null
  const responseEntries = buildResponseEntries(gt)

  return (
    <div className="space-y-3">
      {vagueReport && (
        <div>
          <div className="text-[10px] text-gray-400 mb-1">The opening report:</div>
          <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-700 italic border-l-2 border-gray-300">
            &ldquo;{vagueReport}&rdquo;
          </div>
        </div>
      )}

      <div>
        <div className="text-[10px] text-gray-400 mb-1.5">Pick a response:</div>
        <div className="space-y-2">
          {responseEntries.map((r) => (
            <div key={r.key} className="bg-white border border-gray-200 rounded-lg p-2.5 hover:border-teal-300 transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-semibold text-teal-700 mb-0.5">{r.label}</div>
                  <div className="text-xs text-gray-800">&ldquo;{r.text}&rdquo;</div>
                </div>
                <CopyButton text={r.text} />
              </div>
              {(r.hint || r.correctCause) && (
                <div className="mt-1.5 text-[10px] text-gray-400">
                  {r.correctCause && <span>Root cause: {r.correctCause}</span>}
                  {!r.correctCause && r.hint && <span>{r.hint}</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shape B: Simple conversation flow (single user_response string)
// ---------------------------------------------------------------------------

function HitlGuidanceShapeB({
  flow,
  keys,
}: {
  flow: Record<string, unknown>
  keys: string[]
}) {
  const steps = keys
    .filter((k) => typeof flow[k] === 'string')
    .map((k) => ({ key: k, label: humanizeKey(k), text: String(flow[k]) }))

  const responseStep = steps.find((s) => s.key.includes('user_response') || s.key.includes('response'))

  const STEP_STYLES: Record<string, { color: string }> = {
    vague: { color: 'gray' },
    clarification: { color: 'blue' },
    response: { color: 'green' },
    focused: { color: 'purple' },
    correct: { color: 'green' },
  }

  function getStyle(key: string) {
    if (key.includes('vague')) return STEP_STYLES.vague
    if (key.includes('clarification') || key.includes('asks')) return STEP_STYLES.clarification
    if (key.includes('response')) return STEP_STYLES.response
    if (key.includes('focused') || key.includes('investigation')) return STEP_STYLES.focused
    if (key.includes('correct') || key.includes('root_cause')) return STEP_STYLES.correct
    return STEP_STYLES.vague
  }

  return (
    <div className="space-y-2">
      {steps.map((step) => {
        const style = getStyle(step.key)
        const isResponse = step === responseStep
        const isVague = step.key.includes('vague')

        return (
          <div key={step.key}>
            <div className="text-[10px] text-gray-400 mb-0.5">{step.label}:</div>
            {isVague || isResponse ? (
              <div className={`flex items-start gap-2 rounded-lg px-3 py-2 border-l-2 ${
                isResponse ? 'bg-green-50 border-l-green-400' : 'bg-gray-50 border-l-gray-300'
              }`}>
                <span className={`flex-1 text-xs ${isResponse ? 'text-green-800' : 'text-gray-700'} italic`}>
                  &ldquo;{step.text}&rdquo;
                </span>
                {isResponse && <CopyButton text={step.text} />}
              </div>
            ) : (
              <div className={`text-[11px] leading-relaxed ${
                style.color === 'green' ? 'text-green-700 font-medium' : 'text-gray-600'
              }`}>
                {step.text}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

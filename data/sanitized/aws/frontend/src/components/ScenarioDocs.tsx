import { useEffect, useState } from 'react'
import { fetchScenarioDocs } from '../api/client'
import type { ScenarioDocs as ScenarioDocsType, GroundTruth } from '../types/investigation'
import HitlGuidance from './HitlGuidance'
import AnswerKey, { getTrap, getWhyText } from './AnswerKey'
import { extractDomainTag } from '../utils/domainTags'

interface Props {
  scenarioName: string
  open: boolean
  onClose: () => void
  /** Pre-fetched docs (skip internal fetch when provided) */
  docs?: ScenarioDocsType | null
}

// ---------------------------------------------------------------------------
// Collapsible section wrapper
// ---------------------------------------------------------------------------

function Section({
  title,
  badge,
  defaultOpen = true,
  children,
}: {
  title: string
  badge?: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border-t border-gray-100 first:border-t-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 transition-colors text-left"
      >
        <svg
          className={`w-3 h-3 text-gray-400 flex-none transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">{title}</span>
        {badge && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">{badge}</span>
        )}
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scenario overview (always shown, not collapsible)
// ---------------------------------------------------------------------------

function ScenarioOverview({ gt, scenarioName }: { gt: GroundTruth; scenarioName: string }) {
  const domain = extractDomainTag(gt.domain ?? scenarioName.replace(/-/g, ' '))

  return (
    <div className="px-4 py-3 space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${domain.bg} ${domain.text}`}>
          {domain.label}
        </span>
        {gt.difficulty && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200 font-medium">
            {gt.difficulty}
          </span>
        )}
      </div>
      {gt.description && (
        <p className="text-xs text-gray-600 leading-relaxed">{gt.description}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Watch Out (non-HITL trap / red herrings)
// ---------------------------------------------------------------------------

function WatchOut({ gt }: { gt: GroundTruth }) {
  const trap = getTrap(gt)
  const redHerrings = gt.red_herrings

  if (!trap && !redHerrings?.length) return null

  return (
    <div className="space-y-2.5">
      {trap && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
          {trap.obvious_answer && (
            <div className="mb-1.5">
              <span className="text-[10px] font-bold text-amber-700">Trap: </span>
              <span className="text-xs text-amber-900">&ldquo;{trap.obvious_answer}&rdquo;</span>
            </div>
          )}
          {trap.why_wrong && (
            <p className="text-[11px] text-amber-800 leading-relaxed">{trap.why_wrong}</p>
          )}
        </div>
      )}

      {redHerrings && redHerrings.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Red Herrings</div>
          <ul className="space-y-0.5">
            {redHerrings.map((rh, i) => (
              <li key={i} className="text-[11px] text-gray-600 pl-3 relative before:content-[''] before:absolute before:left-0 before:top-[7px] before:w-1.5 before:h-1.5 before:bg-amber-300 before:rounded-full">
                {typeof rh === 'string' ? rh : rh.name ?? rh.evidence ?? ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Log viewer with severity highlighting and search
// ---------------------------------------------------------------------------

function LogViewer({ content }: { content: string }) {
  const [search, setSearch] = useState('')
  const lines = content.split('\n')
  const searchLower = search.toLowerCase()
  const filtered = search ? lines.filter((l) => l.toLowerCase().includes(searchLower)) : lines

  return (
    <div className="space-y-2">
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter logs..."
          className="w-full text-[11px] border border-gray-200 rounded-lg px-3 py-1.5 pl-7 focus:ring-1 focus:ring-teal-400 focus:border-teal-400 bg-white"
        />
        <svg className="absolute left-2.5 top-[7px] w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        {search && (
          <span className="absolute right-2.5 top-[6px] text-[10px] text-gray-400">
            {filtered.length}/{lines.length}
          </span>
        )}
      </div>
      <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-y-auto max-h-[50vh] font-mono text-[11px] leading-[1.7]">
        {filtered.map((line, i) => (
          <LogLine key={i} line={line} highlight={searchLower} />
        ))}
        {filtered.length === 0 && (
          <div className="p-4 text-center text-gray-400 text-xs">No matching lines</div>
        )}
      </div>
    </div>
  )
}

function LogLine({ line, highlight }: { line: string; highlight: string }) {
  if (!line.trim()) return <div className="h-2" />
  const isError = /\bERROR\b/.test(line)
  const isWarn = /\bWARN\b/.test(line)
  const bg = isError ? 'bg-red-50' : isWarn ? 'bg-amber-50/60' : ''
  const border = isError ? 'border-l-2 border-l-red-400' : isWarn ? 'border-l-2 border-l-amber-300' : 'border-l-2 border-l-transparent'
  const match = line.match(/^(\S+)\s+(ERROR|WARN|INFO)\s+(.*)$/)

  return (
    <div className={`px-3 py-0.5 ${bg} ${border} hover:bg-gray-100/50`}>
      {match ? (
        <>
          <span className="text-gray-400">{match[1]}</span>{' '}
          <span className={match[2] === 'ERROR' ? 'text-red-600 font-semibold' : match[2] === 'WARN' ? 'text-amber-600 font-medium' : 'text-gray-400'}>
            {match[2]}
          </span>{' '}
          <span className="text-gray-700">{maybeHighlight(match[3], highlight)}</span>
        </>
      ) : (
        <span className="text-gray-600">{maybeHighlight(line, highlight)}</span>
      )}
    </div>
  )
}

function maybeHighlight(text: string, search: string) {
  if (!search) return text
  const idx = text.toLowerCase().indexOf(search)
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-200 text-yellow-900 rounded-sm px-0.5">{text.slice(idx, idx + search.length)}</mark>
      {text.slice(idx + search.length)}
    </>
  )
}

// ---------------------------------------------------------------------------
// Logs section (collapsible, wraps LogViewer)
// ---------------------------------------------------------------------------

function LogsSection({ evidence }: { evidence: Record<string, string> }) {
  const files = Object.keys(evidence)
  const [selected, setSelected] = useState(files[0] ?? '')

  if (files.length === 0) return null

  return (
    <div>
      {files.length > 1 && (
        <div className="flex gap-1 mb-2 flex-wrap">
          {files.map((f) => (
            <button
              key={f}
              onClick={() => setSelected(f)}
              className={`text-[11px] px-2 py-1 rounded-md border transition-colors ${
                f === selected
                  ? 'bg-teal-50 border-teal-300 text-teal-700 font-medium'
                  : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      )}
      {files.length === 1 && (
        <div className="text-[11px] text-gray-400 font-mono mb-2">{files[0]}</div>
      )}
      {selected && evidence[selected] && (
        selected.endsWith('.log')
          ? <LogViewer content={evidence[selected]} />
          : <pre className="text-[11px] bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words max-h-[50vh] overflow-y-auto font-mono text-gray-700">{evidence[selected]}</pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ScenarioDocs({ scenarioName, open, onClose, docs: externalDocs }: Props) {
  const [internalDocs, setInternalDocs] = useState<ScenarioDocsType | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Use externally-provided docs if available, otherwise fetch
  const docs = externalDocs ?? internalDocs

  useEffect(() => {
    if (externalDocs) return // skip fetch when docs are provided externally
    setInternalDocs(null)
    setError(null)
    fetchScenarioDocs(scenarioName)
      .then(setInternalDocs)
      .catch(() => setError('Failed to load scenario docs'))
  }, [scenarioName, externalDocs])

  if (!open) return null

  const gt = docs?.ground_truth
  const evidenceCount = docs ? Object.keys(docs.evidence).length : 0
  const trap = gt ? getTrap(gt) : null
  const whyText = gt ? getWhyText(gt) : null

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex-none flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50/50">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Scenario Reference</h3>
          <p className="text-[11px] text-gray-500 capitalize">{scenarioName.replace(/-/g, ' ')}</p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-100"
          aria-label="Close docs panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="p-4 text-sm text-red-600">{error}</div>
        )}

        {!docs && !error && (
          <div className="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
            <div className="w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            Loading...
          </div>
        )}

        {docs && gt && (
          <>
            {/* Overview (always visible) */}
            <ScenarioOverview gt={gt} scenarioName={scenarioName} />

            {/* What To Say */}
            <Section title="What To Say" defaultOpen={true}>
              <HitlGuidance gt={gt} />
            </Section>

            {/* Answer Key */}
            <Section title="Answer Key" defaultOpen={false}>
              <AnswerKey gt={gt} />
            </Section>

            {/* Watch Out (shown when trap/red_herring data exists) */}
            {(trap || gt.red_herrings?.length) && (
              <Section title="Watch Out" defaultOpen={false}>
                <WatchOut gt={gt} />
              </Section>
            )}

            {/* Why This Matters */}
            {whyText && (
              <Section title="Why This Matters" defaultOpen={false}>
                <p className="text-[11px] text-gray-600 leading-relaxed whitespace-pre-line">{whyText}</p>
              </Section>
            )}

            {/* Logs */}
            {evidenceCount > 0 && (
              <Section title="Logs" badge={String(evidenceCount)} defaultOpen={false}>
                <LogsSection evidence={docs.evidence} />
              </Section>
            )}
          </>
        )}

        {/* Fallback: no ground truth, just show logs */}
        {docs && !gt && evidenceCount > 0 && (
          <Section title="Logs" badge={String(evidenceCount)} defaultOpen={true}>
            <LogsSection evidence={docs.evidence} />
          </Section>
        )}
      </div>
    </div>
  )
}

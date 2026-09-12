import type { Scenario, Phase } from '../types/investigation'
import { extractDomainTag } from '../utils/domainTags'
import { humanize } from '../utils/format'

export interface RunningInvestigation {
  name: string
  phase: Phase
  hasInterrupt: boolean
}

interface Props {
  scenarios: Scenario[]
  selected: string | null
  running: RunningInvestigation[]
  onSelect: (name: string) => void
}

function phaseLabel(phase: Phase, hasInterrupt: boolean): string {
  if (hasInterrupt) return 'Awaiting input'
  if (phase === 'stopped') return 'Paused'
  if (phase === 'complete') return 'Complete'
  return 'Investigating'
}

export default function ScenarioRail({ scenarios, selected, running, onSelect }: Props) {
  const runningNames = new Set(running.map((r) => r.name))
  const availableScenarios = scenarios.filter((s) => !runningNames.has(s.name))

  return (
    <div className="flex-none flex flex-col bg-white border-r border-gray-200 w-[320px] overflow-hidden">
      {/* Active investigations section */}
      {running.length > 0 && (
        <div className="flex-none bg-teal-50/40">
          <div className="px-3 py-2.5 border-b border-teal-100">
            <span className="text-[10px] font-semibold text-teal-600 uppercase tracking-wide">
              Active ({running.length})
            </span>
          </div>
          {running.map((inv) => {
            const isViewing = inv.name === selected
            const isComplete = inv.phase === 'complete'
            const isStopped = inv.phase === 'stopped'
            return (
              <button
                key={inv.name}
                onClick={() => onSelect(inv.name)}
                className={`w-full text-left px-3 py-2.5 transition-colors ${
                  isViewing ? 'bg-teal-100/70' : 'hover:bg-teal-100/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`flex-none w-2 h-2 rounded-full ${
                    isComplete
                      ? 'bg-green-500'
                      : isStopped
                        ? 'bg-gray-400'
                        : inv.hasInterrupt
                          ? 'bg-amber-500'
                          : 'bg-teal-500 animate-pulse'
                  }`} />
                  <span className="text-sm font-medium text-teal-900 line-clamp-2 flex-1">
                    {humanize(inv.name)}
                  </span>
                </div>
                <div className="ml-4 mt-0.5">
                  <span className={`text-[10px] ${
                    isComplete ? 'text-green-600' : isStopped ? 'text-gray-500' : inv.hasInterrupt ? 'text-amber-600' : 'text-teal-600'
                  }`}>
                    {phaseLabel(inv.phase, inv.hasInterrupt)}
                  </span>
                </div>
              </button>
            )
          })}
          <div className="border-b border-gray-200" />
        </div>
      )}

      {/* Scenario picker section */}
      <div className="flex-none px-3 py-2.5 border-b border-gray-100">
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
          Scenarios
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {availableScenarios.map((s) => {
          const isSelected = s.name === selected
          const domain = extractDomainTag(s.description)

          return (
            <button
              key={s.name}
              onClick={() => onSelect(s.name)}
              className={`w-full text-left px-3 py-2.5 transition-colors border-l-2 ${
                isSelected
                  ? 'bg-teal-50 border-l-teal-500'
                  : 'border-l-transparent hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium line-clamp-2 ${isSelected ? 'text-teal-700' : 'text-gray-900'}`}>
                  {s.display_name || humanize(s.name)}
                </span>
              </div>
              <div className="mt-1">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${domain.bg} ${domain.text}`}>
                  {domain.label}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

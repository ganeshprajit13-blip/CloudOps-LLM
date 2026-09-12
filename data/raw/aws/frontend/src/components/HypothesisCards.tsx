import type { Hypotheses } from '../types/investigation'
import { HYPOTHESIS_COLORS } from '../utils/colors'

interface Props {
  hypotheses: Hypotheses
  winnerHypothesis?: number | null
}

const COLORS = HYPOTHESIS_COLORS.map((c) => `${c.border300} ${c.bg50}`)

export default function HypothesisCards({ hypotheses, winnerHypothesis }: Props) {
  const entries = Object.entries(hypotheses).sort(
    ([a], [b]) => Number(a) - Number(b),
  )

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        Generated Hypotheses
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {entries.map(([priority, hyp], i) => {
          const isWinner = winnerHypothesis != null && Number(priority) === winnerHypothesis
          return (
          <div
            key={priority}
            className={`border-l-4 rounded-r-lg p-3 ${isWinner ? 'border-green-400 bg-green-50 ring-2 ring-green-300' : (COLORS[i] || COLORS[4])}`}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[10px] font-bold bg-white/70 px-1.5 py-0.5 rounded">
                {isWinner ? '✓' : '#'}{priority}
              </span>
              <span className="text-xs font-semibold text-gray-900 truncate">
                {hyp.service}
              </span>
            </div>
            <p className="text-xs text-gray-700 line-clamp-2">{hyp.description}</p>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {hyp.search_terms.slice(0, 3).map((term) => (
                <span
                  key={term}
                  className="text-[10px] bg-white/70 text-gray-600 px-1.5 py-0.5 rounded border border-gray-200/50"
                >
                  {term}
                </span>
              ))}
            </div>
          </div>
        )})}
      </div>
    </div>
  )
}

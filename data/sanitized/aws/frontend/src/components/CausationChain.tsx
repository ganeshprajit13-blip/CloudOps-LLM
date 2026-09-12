interface Props {
  chain: Array<{ step: string; service: string }>
}

export default function CausationChain({ chain }: Props) {
  if (chain.length === 0) return null

  const lastIdx = chain.length - 1

  return (
    <div className="flex flex-col items-center py-2">
      {chain.map((c, i) => {
        const isFirst = i === 0
        const isLast = i === lastIdx

        // Pick colors per role
        const ring = isFirst
          ? 'border-red-300 bg-red-50'
          : isLast
            ? 'border-slate-300 bg-slate-50'
            : 'border-teal-200 bg-teal-50/50'

        const badge = isFirst
          ? 'bg-red-100 text-red-700 border-red-200'
          : isLast
            ? 'bg-slate-100 text-slate-600 border-slate-200'
            : 'bg-teal-50 text-teal-600 border-teal-200'

        const label = isFirst ? 'Root Cause' : isLast ? 'Observed Impact' : null

        return (
          <div key={i} className="flex flex-col items-center w-full max-w-md">
            {/* Arrow between nodes */}
            {i > 0 && (
              <svg width="16" height="24" viewBox="0 0 16 24" className="text-gray-300 my-0.5">
                <line x1="8" y1="0" x2="8" y2="18" stroke="currentColor" strokeWidth="2" />
                <polygon points="3,16 8,23 13,16" fill="currentColor" />
              </svg>
            )}

            {/* Node */}
            <div className={`w-full rounded-lg border px-3.5 py-2.5 ${ring}`}>
              {label && (
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">
                  {label}
                </span>
              )}
              <p className="text-sm text-gray-800 leading-snug">{c.step}</p>
              <span className={`inline-block text-[10px] font-mono px-1.5 py-0.5 mt-1.5 rounded border ${badge}`}>
                {c.service}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

import { humanize } from '../utils/format'

interface Props {
  scenarioName: string | null
  displayName?: string | null
  isInvestigating: boolean
  onNavigate: (level: 'browse' | 'preview' | 'investigating') => void
}

export default function Breadcrumb({ scenarioName, displayName, isInvestigating, onNavigate }: Props) {
  return (
    <div className="flex items-center gap-1 text-sm">
      <button
        onClick={() => onNavigate('browse')}
        className={`flex items-center gap-1.5 transition-colors ${
          scenarioName
            ? 'text-slate-400 hover:text-slate-200 cursor-pointer'
            : 'text-white font-bold cursor-default'
        }`}
      >
        <img src="/favicon.svg" alt="" className="h-5 w-5" />
        RCA Deep Research
      </button>

      {scenarioName && (
        <>
          <span className="text-slate-600">/</span>
          <button
            onClick={() => onNavigate('preview')}
            className={`transition-colors truncate max-w-[200px] ${
              isInvestigating
                ? 'text-slate-400 hover:text-slate-200 cursor-pointer'
                : 'text-white font-semibold cursor-default'
            }`}
            title={displayName || humanize(scenarioName)}
          >
            {displayName || humanize(scenarioName)}
          </button>
        </>
      )}

      {isInvestigating && (
        <>
          <span className="text-slate-600">/</span>
          <span className="text-white font-semibold">Investigation</span>
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import type { ContextDetails } from '../types/investigation'

interface Props {
  details: ContextDetails
  summaryText: string
}

export default function ContextDetailsCard({ details, summaryText }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState<'kb' | 'changes' | 'errors'>('kb')

  const kbCount = details.kb_chunks?.length ?? 0
  const changeCount = details.change_signals?.length ?? 0
  const errorCount = details.error_signals?.length ?? 0

  const tabs: { key: 'kb' | 'changes' | 'errors'; label: string; count: number }[] = []
  if (kbCount > 0) tabs.push({ key: 'kb', label: 'KB Chunks', count: kbCount })
  if (changeCount > 0) tabs.push({ key: 'changes', label: 'Change Signals', count: changeCount })
  if (errorCount > 0) tabs.push({ key: 'errors', label: 'Error Signals', count: errorCount })

  // Default to the first available tab
  const effectiveTab = tabs.find((t) => t.key === activeTab) ? activeTab : tabs[0]?.key ?? 'kb'

  const items =
    effectiveTab === 'kb'
      ? details.kb_chunks
      : effectiveTab === 'changes'
        ? details.change_signals
        : details.error_signals

  return (
    <div className="animate-messageIn">
      <div className="flex gap-3">
        <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-sm mt-0.5">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
          </svg>
        </div>
        <div className="flex-1 min-w-0 max-w-[85%]">
          <div className="text-[10px] text-gray-400 font-medium mb-1 ml-1 uppercase tracking-wider">
            context enrichment
          </div>
          <div className="bg-white border border-gray-200/80 rounded-2xl rounded-tl-sm shadow-sm overflow-hidden">
            {/* Collapsible header */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="w-full flex items-center gap-2.5 px-4 py-3 text-left hover:bg-gray-50/50 transition-colors"
            >
              <svg
                className={`w-3.5 h-3.5 text-gray-400 flex-none transition-transform ${expanded ? 'rotate-90' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span className="text-sm text-gray-800">{summaryText}</span>
              <span className="text-xs text-gray-400 ml-auto flex-none">
                click to inspect
              </span>
            </button>

            {/* Expanded content */}
            {expanded && (
              <div className="border-t border-gray-100">
                {/* Tabs */}
                {tabs.length > 1 && (
                  <div className="flex gap-1 px-4 pt-2">
                    {tabs.map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors ${
                          effectiveTab === tab.key
                            ? 'bg-teal-100 text-teal-700'
                            : 'text-gray-500 hover:bg-gray-100'
                        }`}
                      >
                        {tab.label} ({tab.count})
                      </button>
                    ))}
                  </div>
                )}

                {/* Content */}
                <div className="px-4 py-3 space-y-2 max-h-[400px] overflow-y-auto">
                  {items && items.length > 0 ? (
                    items.map((item, i) => (
                      <div key={i} className="border border-gray-200 rounded-lg bg-gray-50/50">
                        <pre className="text-[11px] text-gray-600 p-2.5 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                          {item}
                        </pre>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-gray-400 italic">No data</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

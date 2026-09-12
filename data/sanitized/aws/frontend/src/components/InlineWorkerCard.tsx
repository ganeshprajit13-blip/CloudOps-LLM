import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Hypothesis, StreamMessage, ToolCallInfo } from '../types/investigation'
import { interleaveEntries } from '../utils/interleave'

interface Props {
  priority: string
  hypothesis: Hypothesis | null
  messages: StreamMessage[]
  toolCalls: ToolCallInfo[]
  isComplete: boolean
  conclusion: string | null
}

export default function InlineWorkerCard({ priority, hypothesis, messages, toolCalls, isComplete, conclusion }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [toolsExpanded, setToolsExpanded] = useState<Set<number>>(new Set())

  const toggleTool = (idx: number) => {
    setToolsExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const hasActiveStream = messages.some((m) => m.isStreaming)
  const activeTool = toolCalls.find((tc) => !tc.result)
  const isActive = !isComplete && (hasActiveStream || !!activeTool || messages.length > 0)
  const serviceName = hypothesis?.service ?? `Investigator ${priority}`

  const entries = interleaveEntries(messages, toolCalls)

  return (
    <div className="animate-messageIn">
      <div className="flex gap-3">
        <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-sm mt-0.5">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0 max-w-[85%]">
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

              {isComplete ? (
                <span className="text-green-600 text-sm font-bold flex-none">{'\u2713'}</span>
              ) : isActive ? (
                <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse flex-none" />
              ) : (
                <span className="inline-block w-2 h-2 bg-gray-300 rounded-full flex-none" />
              )}

              <span className="text-[10px] font-bold text-teal-600 bg-teal-50 px-1.5 py-0.5 rounded flex-none">
                #{priority}
              </span>
              <span className="text-sm font-medium text-gray-800 truncate">
                {serviceName}
              </span>

              {/* Conclusion tag */}
              {conclusion && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex-none bg-gray-100 text-gray-600">
                  {conclusion}
                </span>
              )}

              <span className="text-xs text-gray-400 ml-auto flex-none inline-flex items-center gap-1.5">
                {isComplete ? (
                  `${toolCalls.length} tools`
                ) : activeTool ? (
                  <>
                    <span className="inline-flex items-center gap-1">
                      <svg className="w-3 h-3 text-amber-500 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      {activeTool.name}()
                    </span>
                    {toolCalls.length > 1 && (
                      <>
                        <span className="text-gray-300">|</span>
                        <span>{toolCalls.length} tools</span>
                      </>
                    )}
                  </>
                ) : hasActiveStream ? (
                  <>
                    <span>thinking...</span>
                    {toolCalls.length > 0 && (
                      <>
                        <span className="text-gray-300">|</span>
                        <span>{toolCalls.length} tools</span>
                      </>
                    )}
                  </>
                ) : toolCalls.length > 0 ? (
                  `${toolCalls.length} tools`
                ) : messages.length > 0 ? (
                  'investigating\u2026'
                ) : (
                  'queued'
                )}
              </span>
            </button>

            {/* Expanded content */}
            {expanded && (
              <div className="border-t border-gray-100">
                {hypothesis && (
                  <div className="px-4 py-2 bg-gray-50/50 border-b border-gray-100">
                    <div className="text-xs text-gray-600">{hypothesis.description}</div>
                    {hypothesis.search_terms.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {hypothesis.search_terms.slice(0, 5).map((term) => (
                          <span key={term} className="text-[10px] bg-gray-200/70 text-gray-600 px-1.5 py-0.5 rounded">
                            {term}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="px-4 py-3 space-y-2 max-h-[400px] overflow-y-auto">
                  {entries.length === 0 ? (
                    <div className="text-xs text-gray-400 italic">No activity yet</div>
                  ) : (
                    entries.map((entry, i) => {
                      if (entry.kind === 'message') {
                        return (
                          <div key={entry.msg.id} className="text-sm">
                            <div className="prose prose-sm max-w-none text-gray-700 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                              <ReactMarkdown>{entry.msg.content}</ReactMarkdown>
                              {entry.msg.isStreaming && (
                                <span className="inline-block w-0.5 h-4 bg-teal-500 animate-pulse align-text-bottom ml-0.5" />
                              )}
                            </div>
                          </div>
                        )
                      }

                      const tc = entry.tc
                      const isOpen = toolsExpanded.has(i)
                      return (
                        <div key={`tool-${i}`} className="border border-gray-200 rounded-lg bg-gray-50/50">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleTool(i) }}
                            className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left hover:bg-gray-100/50 transition-colors"
                          >
                            <svg className="w-3.5 h-3.5 text-amber-500 flex-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span className="text-xs font-mono font-medium text-gray-700 flex-1 truncate">
                              {tc.name}()
                            </span>
                            {tc.result ? (
                              <span className="text-xs text-green-600 font-medium flex-none">{'\u2713'}</span>
                            ) : (
                              <svg className="w-3 h-3 text-amber-500 animate-spin flex-none" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                              </svg>
                            )}
                            <svg
                              className={`w-3 h-3 text-gray-400 transition-transform flex-none ${isOpen ? 'rotate-180' : ''}`}
                              fill="none" viewBox="0 0 24 24" stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                          {isOpen && (
                            <div className="px-2.5 pb-2 space-y-1.5 border-t border-gray-200">
                              <div>
                                <div className="text-[10px] text-gray-400 font-medium mt-1.5">Args</div>
                                <pre className="text-[10px] text-gray-600 bg-white rounded p-1.5 overflow-x-auto max-h-[100px]">
                                  {JSON.stringify(tc.args, null, 2)}
                                </pre>
                              </div>
                              {tc.result && (
                                <div>
                                  <div className="text-[10px] text-gray-400 font-medium">Result</div>
                                  <pre className="text-[10px] text-gray-600 bg-white rounded p-1.5 overflow-x-auto max-h-[150px] whitespace-pre-wrap">
                                    {tc.result.length > 500 ? tc.result.slice(0, 500) + '...' : tc.result}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })
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

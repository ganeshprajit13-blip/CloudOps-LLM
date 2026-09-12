import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useInvestigation, initialState } from './hooks/useInvestigation'
import type { Scenario, ScenarioDocs as ScenarioDocsType, ViewMode } from './types/investigation'
import { fetchScenarios, fetchScenarioDocs } from './api/client'
import { useAuth } from './auth/AuthProvider'
import HypothesisCards from './components/HypothesisCards'
import ScenarioDetail from './components/ScenarioDetail'
import ScenarioRail from './components/ScenarioRail'
import Breadcrumb from './components/Breadcrumb'
import ClarificationContextCard from './components/ClarificationContextCard'
import InlineWorkerCard from './components/InlineWorkerCard'
import ContextDetailsCard from './components/ContextDetailsCard'
import CreateScenarioGuide from './components/CreateScenarioGuide'
import SettingsPanel from './components/SettingsPanel'

export default function App() {
  const { user, loading: authLoading, authEnabled, handleSignIn, handleSignOut } = useAuth()
  const { investigations, start, respond, stop, reset } = useInvestigation()
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [input, setInput] = useState('')
  const [docsOpen, setDocsOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>({ kind: 'browse' })
  const [previewDocs, setPreviewDocs] = useState<ScenarioDocsType | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showEndConfirm, setShowEndConfirm] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [hypothesesOpen, setHypothesesOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [queuedMessage, setQueuedMessage] = useState<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)
  const docsCache = useRef<Map<string, ScenarioDocsType>>(new Map())
  const endConfirmRef = useRef<HTMLDivElement>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const isInvestigating = viewMode.kind === 'investigating'
  const viewScenarioName = viewMode.kind !== 'browse' ? viewMode.scenarioName : null
  const state = viewScenarioName ? (investigations[viewScenarioName] ?? initialState) : initialState
  const isActive = state.phase !== 'idle'
  const runningScenarios = Object.entries(investigations)
    .filter(([, inv]) => inv.phase !== 'idle')
    .map(([name, inv]) => ({ name, phase: inv.phase, hasInterrupt: !!inv.interrupt }))

  useEffect(() => {
    fetchScenarios().then(setScenarios).catch((err) => console.error('Failed to load scenarios:', err))
  }, [])

  useEffect(() => {
    if (state.interrupt) {
      // Auto-send queued message when interrupt arrives
      if (queuedMessage && viewScenarioName) {
        const msg = queuedMessage
        setQueuedMessage(null)
        setInput('')
        respond(viewScenarioName, msg)
        return
      }
      inputRef.current?.focus()
    }
  }, [state.interrupt]) // eslint-disable-line react-hooks/exhaustive-deps

  // Smart autoscroll: stick to bottom unless the user scrolls up
  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  }, [])

  const lastMsgContent = state.messages[state.messages.length - 1]?.content
  useEffect(() => {
    if (stickToBottom.current) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [state.messages.length, state.hypotheses, state.interrupt, lastMsgContent, state.report, queuedMessage])

  // Auto-collapse hypotheses when investigation starts; re-expand during review
  useEffect(() => {
    if (state.phase === 'investigation') setHypothesesOpen(false)
    else if (state.phase === 'hypothesis_review') setHypothesesOpen(true)
  }, [state.phase])

  // Close end-investigation popover on outside click
  useEffect(() => {
    if (!showEndConfirm) return
    const handler = (e: MouseEvent) => {
      if (endConfirmRef.current && !endConfirmRef.current.contains(e.target as Node)) {
        setShowEndConfirm(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showEndConfirm])

  // Close user menu on outside click
  useEffect(() => {
    if (!showUserMenu) return
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showUserMenu])

  // Auto-resize textarea when input changes programmatically (e.g. from sidebar suggestion)
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = input ? `${Math.min(el.scrollHeight, 160)}px` : 'auto'
  }, [input])

  // Group investigator messages into inline worker cards
  const displayItems = useMemo(() => {
    const items: Array<
      | { type: 'message'; msg: typeof state.messages[0] }
      | { type: 'worker'; workerId: string; priority: string }
    > = []
    const seenWorkers = new Set<string>()

    for (const msg of state.messages) {
      const match = msg.node.match(/^investigator-(\d+)/)
      if (match) {
        const baseId = `investigator-${match[1]}`
        if (!seenWorkers.has(baseId)) {
          seenWorkers.add(baseId)
          items.push({ type: 'worker', workerId: baseId, priority: match[1] })
        }
      } else if (!(msg.role === 'system' && msg.toolCall)) {
        items.push({ type: 'message', msg })
      }
    }
    return items
  }, [state.messages])

  const handleSend = () => {
    const val = input.trim()
    if (!val || !viewScenarioName) return
    // If agent is working (no interrupt), queue the message for later
    if (!state.interrupt && state.phase !== 'stopped' && state.phase !== 'complete' && state.phase !== 'idle') {
      setQueuedMessage(val)
      setInput('')
      if (inputRef.current) inputRef.current.style.height = 'auto'
      return
    }
    if (!state.interrupt && state.phase !== 'stopped') return
    setInput('')
    if (inputRef.current) inputRef.current.style.height = 'auto'
    respond(viewScenarioName, val)
  }

  const handleQuickAction = (text: string) => {
    if (viewScenarioName) respond(viewScenarioName, text)
  }

  /** Fetch scenario docs with caching */
  const loadDocs = useCallback((name: string) => {
    const cached = docsCache.current.get(name)
    if (cached) {
      setPreviewDocs(cached)
      setPreviewLoading(false)
      return
    }
    setPreviewDocs(null)
    setPreviewLoading(true)
    fetchScenarioDocs(name)
      .then((docs) => {
        docsCache.current.set(name, docs)
        setPreviewDocs(docs)
      })
      .catch((err) => console.error('Failed to load scenario docs:', err))
      .finally(() => setPreviewLoading(false))
  }, [])

  /** Get cached docs for the active investigation scenario */
  const activeDocs = viewScenarioName ? docsCache.current.get(viewScenarioName) ?? null : null

  /** Handle scenario selection from rail */
  const handleScenarioSelect = useCallback((name: string) => {
    // If clicking a scenario with an active investigation, jump to it
    const inv = investigations[name]
    if (inv && inv.phase !== 'idle') {
      setViewMode({ kind: 'investigating', scenarioName: name })
      loadDocs(name)
      return
    }
    setViewMode({ kind: 'preview', scenarioName: name })
    loadDocs(name)
  }, [loadDocs, investigations])

  /** Handle breadcrumb navigation */
  const handleBreadcrumbNavigate = useCallback((level: 'browse' | 'preview' | 'investigating') => {
    if (level === 'browse') {
      setViewMode({ kind: 'browse' })
    } else if (level === 'preview' && viewScenarioName) {
      setViewMode({ kind: 'preview', scenarioName: viewScenarioName })
      loadDocs(viewScenarioName)
    } else if (level === 'investigating' && viewScenarioName) {
      setViewMode({ kind: 'investigating', scenarioName: viewScenarioName })
    }
  }, [viewScenarioName, loadDocs])

  /** Handle starting an investigation from scenario detail */
  const handleStart = useCallback((scenarioName: string, prompt: string) => {
    stickToBottom.current = true
    setViewMode({ kind: 'investigating', scenarioName })
    start(scenarioName, prompt)
  }, [start])

  /** Handle full reset */
  const handleReset = useCallback(() => {
    if (viewScenarioName) reset(viewScenarioName)
    setViewMode({ kind: 'browse' })
    setDocsOpen(false)
    setQueuedMessage(null)
  }, [reset, viewScenarioName])


  // Auth loading: show spinner while checking session
  if (authEnabled && authLoading) {
    return (
      <div className="flex flex-col h-screen bg-gray-50">
        <header className="flex-none bg-slate-900 border-b border-slate-800 px-6 py-3">
          <div className="flex items-center">
            <span className="text-sm font-semibold text-white tracking-tight">Deep Research RCA</span>
          </div>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3 text-gray-400">
            <div className="w-5 h-5 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Checking authentication...</span>
          </div>
        </div>
      </div>
    )
  }

  // Auth gate: require sign-in before accessing the app
  if (authEnabled && !authLoading && !user) {
    return (
      <div className="flex flex-col h-screen bg-gray-50">
        <header className="flex-none bg-slate-900 border-b border-slate-800 px-6 py-3">
          <div className="flex items-center">
            <span className="text-sm font-semibold text-white tracking-tight">Deep Research RCA</span>
          </div>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-6 max-w-sm">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-100 rounded-full">
              <svg className="w-8 h-8 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Sign in required</h1>
              <p className="text-sm text-gray-500 mt-2">
                Authenticate to access incident investigations and scenario data.
              </p>
            </div>
            <button
              onClick={handleSignIn}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors shadow-sm"
            >
              Sign in
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="flex-none bg-slate-900 border-b border-slate-800 px-6 py-3">
        <div className="flex items-center justify-between">
          <Breadcrumb
            scenarioName={viewScenarioName}
            displayName={viewScenarioName ? scenarios.find(s => s.name === viewScenarioName)?.display_name : null}
            isInvestigating={isInvestigating}
            onNavigate={handleBreadcrumbNavigate}
          />
          <div className="flex items-center gap-3">
            {/* Investigation actions */}
            {isActive && state.scenarioName && (
              <button
                onClick={() => { setDocsOpen(!docsOpen); if (!docsOpen) setSettingsOpen(false) }}
                className={`text-xs px-3 py-1.5 rounded-md border flex items-center gap-1.5 transition-colors ${
                  docsOpen
                    ? 'bg-teal-500/20 border-teal-400 text-teal-300 font-medium'
                    : 'text-slate-400 hover:text-slate-200 border-slate-600 hover:bg-slate-800'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Docs
              </button>
            )}
            {isActive && (
              <div className="relative" ref={endConfirmRef}>
                <button
                  onClick={() => setShowEndConfirm(!showEndConfirm)}
                  className="text-xs text-red-400 hover:text-red-300 border border-red-800 px-3 py-1.5 rounded-md hover:bg-red-900/30 transition-colors"
                >
                  End Investigation
                </button>
                {showEndConfirm && (
                  <div className="absolute right-0 top-full mt-1.5 w-64 bg-white border border-gray-200 shadow-lg rounded-lg p-3 z-50 animate-fadeIn">
                    <p className="text-xs text-gray-600 mb-3">
                      End this investigation? Progress cannot be recovered.
                    </p>
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setShowEndConfirm(false)}
                        className="text-xs px-3 py-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => { handleReset(); setShowEndConfirm(false) }}
                        className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                      >
                        End
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Backend status gear icon */}
            <button
              onClick={() => { setSettingsOpen(!settingsOpen); if (!settingsOpen) setDocsOpen(false) }}
              className={`p-1.5 rounded-md transition-colors ${
                settingsOpen
                  ? 'bg-teal-500/20 text-teal-300'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
              title="Backend Status"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>

            {/* Divider between actions and user identity */}
            {authEnabled && (isActive || user) && (
              <div className="w-px h-5 bg-slate-700" />
            )}

            {/* User identity */}
            {authEnabled && (
              <div className="relative" ref={userMenuRef}>
                {user ? (
                  <>
                    <button
                      onClick={() => setShowUserMenu(!showUserMenu)}
                      className="w-7 h-7 rounded-full bg-teal-600 hover:bg-teal-500 flex items-center justify-center transition-colors ring-2 ring-transparent hover:ring-teal-400/30"
                      title={user.email || user.username}
                    >
                      <span className="text-xs font-bold text-white">
                        {(user.email || user.username || '?')[0].toUpperCase()}
                      </span>
                    </button>
                    {showUserMenu && (
                      <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-gray-200 shadow-xl rounded-lg overflow-hidden z-50 animate-fadeIn">
                        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
                          <p className="text-xs font-medium text-gray-900 truncate">
                            {user.email || user.username}
                          </p>
                        </div>
                        <div className="py-1">
                          <button
                            onClick={() => { setSettingsOpen(true); setDocsOpen(false); setShowUserMenu(false) }}
                            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center gap-2"
                          >
                            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            Backend Status
                          </button>
                          <button
                            onClick={() => { handleSignOut(); setShowUserMenu(false) }}
                            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center gap-2"
                          >
                            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                            </svg>
                            Sign out
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                ) : !authLoading ? (
                  <button
                    onClick={handleSignIn}
                    className="text-xs text-teal-300 hover:text-teal-200 border border-teal-500 px-3 py-1 rounded-md hover:bg-teal-900/30 transition-colors"
                  >
                    Sign in
                  </button>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main content: rail + workspace + optional docs panel */}
      <div className="flex-1 flex min-h-0">
        {/* Left panel — always show scenario rail */}
        <ScenarioRail
          scenarios={scenarios}
          selected={viewScenarioName}
          running={runningScenarios}
          onSelect={handleScenarioSelect}
        />

        {/* Workspace column */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Collapsible hypothesis section */}
          {isInvestigating && isActive && (state.hypotheses || state.phase === 'hypothesis_generation') && (
            <div className="flex-none border-b border-gray-200 bg-gray-50/50">
              <div className="mx-auto max-w-4xl">
                <button
                  onClick={() => setHypothesesOpen(!hypothesesOpen)}
                  className="w-full flex items-center justify-between px-6 py-2 hover:bg-gray-100/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <svg
                      className={`w-3 h-3 text-gray-400 flex-none transition-transform ${hypothesesOpen ? 'rotate-90' : ''}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Hypotheses
                    </span>
                    {state.hypotheses ? (
                      <span className="text-[10px] text-gray-400">
                        {Object.keys(state.hypotheses).length} generated
                      </span>
                    ) : (
                      <span className="text-[10px] text-gray-400 animate-pulse">
                        structuring...
                      </span>
                    )}
                  </div>
                </button>
                {hypothesesOpen && (
                  <div className="px-6 pb-3">
                    {state.hypotheses ? (
                      <HypothesisCards hypotheses={state.hypotheses} winnerHypothesis={state.winnerHypothesis} />
                    ) : (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          Generated Hypotheses
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="border-l-4 border-gray-200 bg-gray-50 rounded-r-lg p-3 animate-pulse">
                              <div className="h-3 bg-gray-200 rounded w-1/3 mb-2" />
                              <div className="h-2.5 bg-gray-200 rounded w-full mb-1" />
                              <div className="h-2.5 bg-gray-200 rounded w-2/3" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Content area */}
          <div className="flex-1 overflow-y-auto" ref={scrollRef} onScroll={handleScroll}>
            <div className="mx-auto px-6 py-6 space-y-4 max-w-4xl">
              {/* Browse mode: welcome content */}
              {viewMode.kind === 'browse' && !isActive && (
                <div className="space-y-6 pt-8 animate-fadeIn">
                  <div className="text-center">
                    <div className="inline-flex items-center justify-center w-12 h-12 bg-teal-100 rounded-full mb-4">
                      <svg className="w-6 h-6 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    <h2 className="text-xl font-bold text-gray-900">Load an Incident</h2>
                    <p className="text-sm text-gray-500 mt-1">
                      Select a scenario from the left to load its incident data, then start the investigation.
                    </p>
                  </div>

                  {/* Create your own scenario hint */}
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
                    <p className="text-xs text-gray-500">
                      Want to investigate your own incidents?{' '}
                      <button
                        onClick={() => setGuideOpen(true)}
                        className="text-teal-600 hover:text-teal-800 font-medium underline underline-offset-2"
                      >
                        Create your own scenario
                      </button>
                    </p>
                  </div>
                </div>
              )}

              {/* Preview mode: scenario detail */}
              {viewMode.kind === 'preview' && (
                <div className="pt-4 animate-fadeIn">
                  {previewLoading || !previewDocs ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="flex items-center gap-3 text-gray-400">
                        <div className="w-5 h-5 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm">Loading scenario...</span>
                      </div>
                    </div>
                  ) : (
                    <ScenarioDetail
                      scenarioName={viewMode.scenarioName}
                      docs={previewDocs}
                      onUsePrompt={(text) => {
                        setInput(text)
                        inputRef.current?.focus()
                      }}
                    />
                  )}
                </div>
              )}

              {/* Investigation mode: chat stream */}
              {isInvestigating && isActive && (
                <div className="animate-fadeIn space-y-5">
                  {displayItems.map((item) => {
                    if (item.type === 'worker') {
                      const wMsgs = state.messages.filter((m) =>
                        (m.node === item.workerId || m.node.startsWith(`${item.workerId}/`)) &&
                        !(m.role === 'system' && m.toolCall),
                      )
                      const wTools = state.toolCalls.filter((tc) =>
                        tc.node === item.workerId || tc.node.startsWith(`${item.workerId}/`),
                      )
                      return (
                        <InlineWorkerCard
                          key={item.workerId}
                          priority={item.priority}
                          hypothesis={state.hypotheses?.[item.priority] ?? null}
                          messages={wMsgs}
                          toolCalls={wTools}
                          isComplete={['synthesis', 'followup', 'stopped', 'complete'].includes(state.phase)}
                          conclusion={state.workerConclusions[item.workerId] ?? null}
                        />
                      )
                    }
                    const msg = item.msg

                    // Render context_enrichment messages as a collapsible card when details are available
                    if (msg.node === 'context_enrichment' && state.contextDetails && !msg.isStreaming) {
                      return (
                        <ContextDetailsCard
                          key={msg.id}
                          details={state.contextDetails}
                          summaryText={msg.content.replace(/\*\*/g, '')}
                        />
                      )
                    }

                    return (
                      <div key={msg.id} className="animate-messageIn">
                        {msg.role === 'human' ? (
                          <div className="flex gap-3 justify-end">
                            <div className="max-w-[80%] bg-gradient-to-br from-teal-600 to-teal-700 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm shadow-md leading-relaxed">
                              {msg.content}
                            </div>
                            <div className="flex-none w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center mt-auto shadow-sm">
                              <svg className="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                              </svg>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-3">
                            <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-sm mt-0.5">
                              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                              </svg>
                            </div>
                            <div className="flex-1 min-w-0 max-w-[85%]">
                              <div className="text-[10px] text-gray-400 font-medium mb-1 ml-1 uppercase tracking-wider">
                                {msg.node.replace(/_/g, ' ')}
                              </div>
                              <div className="bg-white border border-gray-200/80 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                                <div className="prose prose-sm max-w-none text-gray-800 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                                  {msg.isStreaming && (
                                    <span className="inline-block w-0.5 h-4 bg-teal-500 animate-pulse align-text-bottom ml-0.5" />
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {state.report && (
                    <div className="flex gap-3 animate-messageIn">
                      <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-sm mt-0.5">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div className="flex-1 bg-green-50 border border-green-200 rounded-2xl rounded-tl-sm p-4 shadow-sm">
                        <div className="text-xs font-semibold text-green-800 mb-2">Root Cause Analysis</div>
                        <div className="prose prose-sm max-w-none text-gray-800 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                          <ReactMarkdown>{state.report}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  )}

                  {!state.interrupt && state.phase !== 'complete' && state.phase !== 'stopped' && !state.error && !state.messages.some(m => m.isStreaming) && (
                    <div className="flex gap-3">
                      <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-sm">
                        <svg className="w-4 h-4 text-white animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                        </svg>
                      </div>
                      <div className="bg-white border border-gray-200/80 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                        <div className="flex items-center gap-2.5">
                          <div className="flex gap-1">
                            <div className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                          <span className="text-xs text-gray-400 capitalize">{state.phase.replace(/_/g, ' ')}...</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {state.error && (
                    <div className="ml-11 bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm p-4 text-sm text-red-800 shadow-sm">
                      Error: {state.error}
                    </div>
                  )}

                  {queuedMessage && (
                    <div className="flex gap-3 justify-end animate-messageIn">
                      <div className="max-w-[80%]">
                        <div className="bg-gradient-to-br from-amber-500 to-amber-600 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm shadow-md leading-relaxed">
                          {queuedMessage}
                        </div>
                        <div className="text-[10px] text-amber-600 mt-1 text-right">Queued — sending when agent pauses</div>
                      </div>
                      <div className="flex-none w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center mt-auto shadow-sm">
                        <svg className="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>

          {/* Clarification context card (above input during clarification) */}
          {isInvestigating && isActive && state.interrupt?.type === 'clarification' && activeDocs && (
            <ClarificationContextCard
              docs={activeDocs}
              onUseResponse={(text) => setInput(text)}
            />
          )}

          {/* Input bar */}
          <div className="flex-none border-t border-gray-200 bg-white px-6 py-4 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
            <div className="mx-auto max-w-4xl">
              {!isInvestigating || !isActive ? (
                /* Preview mode — active input to start investigation */
                <div className="flex gap-2">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value)
                      e.target.style.height = 'auto'
                      e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        if (viewScenarioName && input.trim()) {
                          handleStart(viewScenarioName, input.trim())
                          setInput('')
                          if (inputRef.current) inputRef.current.style.height = 'auto'
                        }
                      }
                    }}
                    disabled={!viewScenarioName}
                    placeholder={viewScenarioName ? "Describe what you'd like to investigate..." : "Select a scenario to begin..."}
                    rows={1}
                    className={`flex-1 resize-none border rounded-xl px-4 py-2.5 text-sm ${
                      viewScenarioName
                        ? 'border-gray-300 bg-white text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-teal-500'
                        : 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
                    }`}
                  />
                  <button
                    disabled={!viewScenarioName || !input.trim()}
                    onClick={() => {
                      if (viewScenarioName && input.trim()) {
                        handleStart(viewScenarioName, input.trim())
                        setInput('')
                        if (inputRef.current) inputRef.current.style.height = 'auto'
                      }
                    }}
                    className="px-4 py-2.5 bg-teal-600 text-white rounded-xl hover:bg-teal-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              ) : state.phase === 'complete' ? (
                <div className="text-center text-sm text-gray-500 py-1">
                  Investigation complete.{' '}
                  <button onClick={handleReset} className="text-teal-600 hover:text-teal-800 font-medium">
                    Start a new one
                  </button>
                </div>
              ) : (
                /* Active investigation — always show textarea (interrupt, working, or stopped) */
                <div className="space-y-2">
                  {/* Status row */}
                  <div className="flex items-center gap-2">
                    {queuedMessage ? (
                      <>
                        <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                        <span className="text-xs font-medium text-amber-700">
                          Message queued — will send when agent pauses
                        </span>
                        <button
                          onClick={() => setQueuedMessage(null)}
                          className="text-xs text-gray-400 hover:text-gray-600"
                        >
                          Cancel
                        </button>
                      </>
                    ) : null}
                    <div className="flex-1" />
                    {state.interrupt?.type === 'clarification' && state.scenarioName && !docsOpen && (
                      <button
                        onClick={() => setDocsOpen(true)}
                        className="text-xs px-2.5 py-1 text-teal-600 hover:text-teal-800 border border-teal-200 rounded-full hover:bg-teal-50 font-medium"
                      >
                        View scenario docs
                      </button>
                    )}
                    {state.interrupt?.type === 'followup' && (
                      <button
                        onClick={() => handleQuickAction('done')}
                        className="text-xs px-3 py-1 bg-gray-600 text-white rounded-full hover:bg-gray-700 font-medium"
                      >
                        Done
                      </button>
                    )}
                    {!state.interrupt && state.phase !== 'stopped' && (
                      <button
                        onClick={() => viewScenarioName && stop(viewScenarioName)}
                        className="flex items-center gap-1.5 px-3 py-1 bg-gray-700 text-white text-xs rounded-full hover:bg-gray-800 transition-colors"
                      >
                        <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                          <rect x="6" y="6" width="12" height="12" rx="2" />
                        </svg>
                        Stop
                      </button>
                    )}
                  </div>
                  {/* Input row */}
                  <div className="flex gap-2">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value)
                        e.target.style.height = 'auto'
                        e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleSend()
                        }
                      }}
                      placeholder={
                        queuedMessage
                          ? 'Message already queued (press Cancel to change it)'
                          : state.interrupt?.type === 'clarification'
                            ? 'Provide the details the agent asked for...'
                            : state.interrupt?.type === 'hypothesis_review'
                              ? 'Type "go" to investigate all, or "investigate #1 and #2" for specific ones...'
                              : state.interrupt?.type === 'followup'
                                ? 'Ask about the findings...'
                                : state.phase === 'stopped'
                                  ? 'Continue the investigation or ask a question...'
                                  : 'Type ahead — your message will be sent when the agent pauses...'
                      }
                      disabled={!!queuedMessage}
                      rows={1}
                      className={`flex-1 resize-none border rounded-xl px-4 py-2.5 text-sm max-h-[160px] overflow-y-auto ${
                        queuedMessage
                          ? 'border-amber-200 bg-amber-50/50 text-gray-400 cursor-not-allowed'
                          : 'border-gray-300 focus:ring-2 focus:ring-teal-500 focus:border-teal-500'
                      }`}
                    />
                    <button
                      onClick={handleSend}
                      disabled={!input.trim() || !!queuedMessage}
                      className="px-4 py-2.5 bg-teal-600 text-white rounded-xl hover:bg-teal-700 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                      </svg>
                    </button>
                  </div>
                  {state.phase === 'stopped' && (
                    <div className="text-center">
                      <button onClick={handleReset} className="text-xs text-gray-400 hover:text-gray-600">
                        Reset investigation
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Scenario docs panel (right side) */}
        {isActive && state.scenarioName && docsOpen && activeDocs && (
          <div className="w-[420px] flex-none flex flex-col h-full bg-white border-l border-gray-200">
            {/* Header */}
            <div className="flex-none flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50/50">
              <h3 className="text-sm font-semibold text-gray-900">Scenario Reference</h3>
              <button
                onClick={() => setDocsOpen(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-100"
                aria-label="Close docs panel"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {/* Scrollable scenario detail */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <ScenarioDetail
                scenarioName={state.scenarioName}
                docs={activeDocs}
                onUsePrompt={(text) => {
                  setInput(text)
                  inputRef.current?.focus()
                }}
              />
            </div>
          </div>
        )}

        {/* Backend status panel (right side) */}
        {settingsOpen && (
          <SettingsPanel onClose={() => setSettingsOpen(false)} />
        )}
      </div>

      {/* Create scenario guide modal */}
      {guideOpen && <CreateScenarioGuide onClose={() => setGuideOpen(false)} />}
    </div>
  )
}

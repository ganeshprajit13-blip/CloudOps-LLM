import type { Scenario, ScenarioDocs, InterruptInfo, Hypotheses, ContextDetails } from '../types/investigation'
import { isProductionMode } from './mode'
import { readSSEStream } from './sse-stream'
import { routeEvent } from './agentcore-client'

const BASE = '/api'

// For SSE streaming in local dev, connect directly to the FastAPI backend to
// bypass the Vite dev-server proxy which buffers chunked responses.  In
// production mode this is unused (AgentCore client handles streaming).
const STREAM_BASE = isProductionMode ? BASE : 'http://localhost:8000/api'

// ---------------------------------------------------------------------------
// Scenario APIs — FastAPI in local dev, static JSON in production
// ---------------------------------------------------------------------------

/** Cached scenario manifest (production mode). */
let _manifestCache: { scenarios: Scenario[]; docs: Record<string, ScenarioDocs> } | null = null

async function getManifest() {
  if (_manifestCache) return _manifestCache
  const res = await fetch('/scenarios.json')
  if (!res.ok) throw new Error('Failed to load scenarios.json')
  _manifestCache = await res.json()
  return _manifestCache!
}

export async function fetchScenarios(): Promise<Scenario[]> {
  if (isProductionMode) {
    const manifest = await getManifest()
    return manifest.scenarios
  }
  const res = await fetch(`${BASE}/scenarios`)
  const data = await res.json()
  return data.scenarios
}

export async function fetchScenario(name: string): Promise<{ name: string; incident: string }> {
  if (isProductionMode) {
    const manifest = await getManifest()
    const docs = manifest.docs[name]
    if (!docs) throw new Error(`Scenario not found: ${name}`)
    return { name, incident: docs.incident || '' }
  }
  const res = await fetch(`${BASE}/scenarios/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`Scenario not found: ${name}`)
  return res.json()
}

export async function fetchScenarioDocs(name: string): Promise<ScenarioDocs> {
  if (isProductionMode) {
    const manifest = await getManifest()
    const docs = manifest.docs[name]
    if (!docs) throw new Error(`Failed to load docs for scenario: ${name}`)
    return docs
  }
  const res = await fetch(`${BASE}/scenarios/${encodeURIComponent(name)}/docs`)
  if (!res.ok) throw new Error(`Failed to load docs for scenario: ${name}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Config / Backend Status — FastAPI only (not available in production mode)
// ---------------------------------------------------------------------------

export interface BackendStatus {
  type: string
  status: 'ok' | 'error' | 'unconfigured'
  message?: string
  details: Record<string, unknown>
}

export interface ConfigStatus {
  agent: { mode: string; region: string }
  backends: {
    log_search: BackendStatus
    context_source: BackendStatus
    checkpoint: BackendStatus
  }
}

export async function fetchConfigStatus(): Promise<ConfigStatus | null> {
  if (isProductionMode) return null
  try {
    const res = await fetch(`${BASE}/config/status`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Investigation APIs — FastAPI only (production uses AgentCore client directly)
// ---------------------------------------------------------------------------

export async function createInvestigation(
  scenarioName?: string,
  incidentText?: string,
): Promise<string> {
  const res = await fetch(`${BASE}/investigations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_name: scenarioName,
      incident_text: incidentText,
    }),
  })
  if (!res.ok) throw new Error('Failed to create investigation')
  const data = await res.json()
  return data.investigation_id
}

export interface StreamHandlers {
  onMessage: (node: string, content: string, role: 'ai' | 'human') => void
  onPhase: (phase: string) => void
  onHypothesis: (hypotheses: Hypotheses) => void
  onContextDetails?: (details: ContextDetails) => void
  onWorkerUpdate: (workerId: string, content: string, conclusion?: string) => void
  onInterrupt: (interrupt: InterruptInfo) => void
  onComplete: (report: string) => void
  onError: (message: string) => void
  onToken?: (content: string, node: string) => void
  onToolCall?: (name: string, args: Record<string, unknown>, node: string) => void
  onToolResult?: (name: string, content: string, node: string) => void
}

/**
 * Stream an investigation via fetch POST + SSE.
 *
 * Start mode (no message): starts the investigation.
 * Resume mode (with message): resumes from HITL interrupt.
 * Stream ends after emitting either 'interrupt' or 'complete'.
 */
export async function streamInvestigation(
  investigationId: string,
  handlers: StreamHandlers,
  message?: string,
): Promise<AbortController> {
  const controller = new AbortController()

  try {
    const response = await fetch(`${STREAM_BASE}/investigations/${investigationId}/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message ?? null }),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      handlers.onError(`Stream error ${response.status}: ${errorText}`)
      return controller
    }

    if (!response.body) {
      handlers.onError('No response body')
      return controller
    }

    // Read stream in background so caller gets the controller immediately for mid-stream abort
    readSSEStream(response, (evt) => routeEvent(evt, handlers), controller.signal).catch(
      (err) => {
        if ((err as Error).name !== 'AbortError') {
          handlers.onError((err as Error).message || 'Stream connection failed')
        }
      },
    )
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      handlers.onError((err as Error).message || 'Stream connection failed')
    }
  }

  return controller
}

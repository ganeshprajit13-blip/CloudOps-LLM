/**
 * AgentCore streaming client for production mode.
 *
 * Follows the FAST (fullstack-solution-template-for-agentcore) pattern:
 * - HTTP POST directly to AgentCore Runtime endpoint with JWT
 * - Reads SSE streaming response via ReadableStream
 * - Parses structured events (same types as FastAPI SSE)
 *
 * HITL model: each invocation is a separate request-response cycle.
 * When an interrupt occurs, the stream ends. The frontend sends a new
 * invocation to resume (AgentCore checkpointer maintains state).
 */

import type { InterruptInfo, Hypotheses, ContextDetails } from '../types/investigation'
import { AGENTCORE_ENDPOINT } from './mode'
import { readSSEStream } from './sse-stream'
import type { SSEEvent } from './sse-stream'

export interface AgentCoreStreamHandlers {
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
 * Route a parsed SSE event to the appropriate handler.
 */
export function routeEvent(evt: SSEEvent, handlers: AgentCoreStreamHandlers): void {
  const { event, data } = evt
  switch (event) {
    case 'message':
      handlers.onMessage(
        (data.node as string) || '',
        (data.content as string) || '',
        (data.role as 'ai' | 'human') || 'ai',
      )
      break
    case 'phase':
      handlers.onPhase((data.phase as string) || '')
      break
    case 'hypothesis':
      handlers.onHypothesis(data.hypotheses as Hypotheses)
      break
    case 'context_details':
      handlers.onContextDetails?.(data as unknown as ContextDetails)
      break
    case 'worker_update':
      handlers.onWorkerUpdate(
        (data.worker_id as string) || '',
        (data.content as string) || '',
        (data.conclusion as string) || undefined,
      )
      break
    case 'interrupt':
      handlers.onInterrupt(data as unknown as InterruptInfo)
      break
    case 'complete':
      handlers.onComplete((data.report as string) || '')
      break
    case 'error':
      handlers.onError((data.message as string) || 'Unknown error')
      break
    case 'token':
      handlers.onToken?.((data.content as string) || '', (data.node as string) || '')
      break
    case 'tool_call':
      handlers.onToolCall?.(
        (data.name as string) || '',
        (data.args as Record<string, unknown>) || {},
        (data.node as string) || '',
      )
      break
    case 'tool_result':
      handlers.onToolResult?.(
        (data.name as string) || '',
        (data.content as string) || '',
        (data.node as string) || '',
      )
      break
    case 'heartbeat':
      break
    default:
      break
  }
}

/**
 * Invoke the AgentCore Runtime with streaming.
 *
 * @param payload - The request payload (message, scenario_name, incident, etc.)
 * @param sessionId - Session ID for checkpoint thread continuity
 * @param accessToken - Cognito JWT access token (null in local dev)
 * @param handlers - Event handlers for streaming events
 * @returns AbortController to cancel the stream
 */
export async function invokeAgentCore(
  payload: Record<string, unknown>,
  sessionId: string,
  accessToken: string | null,
  handlers: AgentCoreStreamHandlers,
): Promise<AbortController> {
  const controller = new AbortController()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId,
  }
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  } else {
    // AgentCore requires Cognito JWT auth — fail fast rather than sending
    // an unauthenticated request that will hang or be silently rejected.
    handlers.onError('Authentication required: no access token available. Please sign in again.')
    return controller
  }

  try {
    const response = await fetch(AGENTCORE_ENDPOINT, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      handlers.onError(`AgentCore error ${response.status}: ${errorText}`)
      return controller
    }

    if (!response.body) {
      handlers.onError('No response body from AgentCore')
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

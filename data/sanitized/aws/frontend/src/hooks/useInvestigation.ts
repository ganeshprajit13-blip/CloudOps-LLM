import { useReducer, useRef, useCallback } from 'react'
import type {
  InvestigationState,
  InvestigationAction,
  InterruptInfo,
  Hypotheses,
  ContextDetails,
  Phase,
  StreamMessage,
  ToolCallInfo,
} from '../types/investigation'
import { createInvestigation, streamInvestigation, fetchScenario } from '../api/client'
import { invokeAgentCore } from '../api/agentcore-client'
import type { AgentCoreStreamHandlers } from '../api/agentcore-client'
import { isProductionMode } from '../api/mode'
import { useAuth } from '../auth/AuthProvider'

export const initialState: InvestigationState = {
  id: null,
  scenarioName: null,
  phase: 'idle',
  messages: [],
  hypotheses: null,
  contextDetails: null,
  interrupt: null,
  report: null,
  winnerHypothesis: null,
  error: null,
  toolCalls: [],
  workerConclusions: {},
}

let msgCounter = 0

function findLastStreamingIndex(messages: StreamMessage[], node: string): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].isStreaming && messages[i].node === node) return i
  }
  return -1
}

function reducer(state: InvestigationState, action: InvestigationAction): InvestigationState {
  switch (action.type) {
    case 'START':
      return { ...initialState, id: action.id, scenarioName: action.scenarioName, phase: 'clarification' }
    case 'PHASE':
      return { ...state, phase: action.phase as Phase }
    case 'TOKEN': {
      // Eagerly advance phase from token metadata so the UI can show
      // placeholders (e.g. hypothesis skeleton) before the node completes
      // and the formal "phase" event arrives.
      const tokenPhase =
        action.node === 'hypothesis_generation' && state.phase !== 'hypothesis_generation'
          ? 'hypothesis_generation' as Phase
          : state.phase

      const streamIdx = findLastStreamingIndex(state.messages, action.node)
      if (streamIdx >= 0) {
        const updated = [...state.messages]
        updated[streamIdx] = {
          ...updated[streamIdx],
          content: updated[streamIdx].content + action.content,
        }
        return { ...state, phase: tokenPhase, messages: updated }
      }
      return {
        ...state,
        phase: tokenPhase,
        messages: [
          ...state.messages,
          {
            id: `msg-${++msgCounter}`,
            node: action.node,
            content: action.content,
            role: 'ai' as const,
            timestamp: Date.now(),
            isStreaming: true,
          },
        ],
      }
    }
    case 'MESSAGE': {
      // If there's already a streaming message for this node, finalize it
      // in-place instead of replacing it. This avoids a visual flash where
      // accumulated tokens disappear and a complete message appears at once.
      const streamIdx = findLastStreamingIndex(state.messages, action.node)
      if (streamIdx >= 0) {
        const updated = [...state.messages]
        updated[streamIdx] = {
          ...updated[streamIdx],
          content: action.content,
          role: action.role,
          isStreaming: false,
        }
        return { ...state, interrupt: null, messages: updated }
      }
      return {
        ...state,
        interrupt: null,
        messages: [
          ...state.messages,
          {
            id: `msg-${++msgCounter}`,
            node: action.node,
            content: action.content,
            role: action.role,
            timestamp: Date.now(),
          },
        ],
      }
    }
    case 'HYPOTHESIS':
      return { ...state, hypotheses: action.hypotheses }
    case 'CONTEXT_DETAILS':
      return { ...state, contextDetails: action.details }
    case 'WORKER_UPDATE': {
      const newConclusions = action.conclusion
        ? { ...state.workerConclusions, [action.worker_id]: action.conclusion }
        : state.workerConclusions
      return {
        ...state,
        workerConclusions: newConclusions,
        messages: [
          ...state.messages,
          {
            id: `msg-${++msgCounter}`,
            node: action.worker_id,
            content: action.content,
            role: 'ai',
            timestamp: Date.now(),
          },
        ],
      }
    }
    case 'TOOL_CALL': {
      const toolCall: ToolCallInfo = {
        name: action.name,
        args: action.args,
        node: action.node,
        timestamp: Date.now(),
      }
      return {
        ...state,
        toolCalls: [...state.toolCalls, toolCall],
        messages: [
          ...state.messages,
          {
            id: `tool-${++msgCounter}`,
            node: action.node,
            content: `Calling **${action.name}**`,
            role: 'system' as const,
            timestamp: Date.now(),
            toolCall: {
              name: action.name,
              args: action.args,
            },
          },
        ],
      }
    }
    case 'TOOL_RESULT': {
      const updated = [...state.messages]
      let matched = false
      // Prefer matching by name + node (avoids cross-worker mismatches)
      for (let i = updated.length - 1; i >= 0; i--) {
        const msg = updated[i]
        if (msg.toolCall && msg.toolCall.name === action.name && msg.node === action.node && !msg.toolCall.result) {
          updated[i] = { ...msg, toolCall: { ...msg.toolCall, result: action.content } }
          matched = true
          break
        }
      }
      // Fallback: match by name only
      if (!matched) {
        for (let i = updated.length - 1; i >= 0; i--) {
          const msg = updated[i]
          if (msg.toolCall && msg.toolCall.name === action.name && !msg.toolCall.result) {
            updated[i] = { ...msg, toolCall: { ...msg.toolCall, result: action.content } }
            break
          }
        }
      }
      const updatedToolCalls = [...state.toolCalls]
      for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
        if (updatedToolCalls[i].name === action.name && updatedToolCalls[i].node === action.node && !updatedToolCalls[i].result) {
          updatedToolCalls[i] = { ...updatedToolCalls[i], result: action.content }
          break
        }
      }
      return { ...state, messages: updated, toolCalls: updatedToolCalls }
    }
    case 'INTERRUPT':
      return { ...state, interrupt: action.interrupt }
    case 'RESPOND':
      return { ...state, interrupt: null }
    case 'COMPLETE':
      return { ...state, phase: 'complete' as Phase, report: action.report, winnerHypothesis: action.winnerHypothesis ?? null, interrupt: null }
    case 'STOP': {
      // Finalize any streaming messages but keep the investigation resumable
      const finalized = state.messages.map((m) =>
        m.isStreaming ? { ...m, isStreaming: false } : m,
      )
      return { ...state, phase: 'stopped', messages: finalized, interrupt: null }
    }
    case 'ERROR':
      return { ...state, error: action.message }
    case 'RESET':
      return initialState
    default:
      return state
  }
}

// ---------------------------------------------------------------------------
// Multi-investigation state
// ---------------------------------------------------------------------------

interface MultiState {
  investigations: Record<string, InvestigationState>
}

type MultiAction =
  | { type: 'DISPATCH'; scenario: string; action: InvestigationAction }

function multiReducer(state: MultiState, action: MultiAction): MultiState {
  const current = state.investigations[action.scenario] ?? initialState
  const next = reducer(current, action.action)
  if (action.action.type === 'RESET') {
    const { [action.scenario]: _, ...rest } = state.investigations
    return { investigations: rest }
  }
  return { investigations: { ...state.investigations, [action.scenario]: next } }
}

/** Build common stream handlers that dispatch to the reducer scoped to a scenario. */
function buildScopedHandlers(dispatch: React.Dispatch<MultiAction>, scenario: string) {
  const d = (action: InvestigationAction) => dispatch({ type: 'DISPATCH', scenario, action })
  return {
    onMessage: (node: string, content: string, role: 'ai' | 'human') =>
      d({ type: 'MESSAGE', node, content, role }),
    onPhase: (phase: string) =>
      d({ type: 'PHASE', phase: phase as Phase }),
    onHypothesis: (hypotheses: Hypotheses) =>
      d({ type: 'HYPOTHESIS', hypotheses }),
    onContextDetails: (details: ContextDetails) =>
      d({ type: 'CONTEXT_DETAILS', details }),
    onWorkerUpdate: (worker_id: string, content: string, conclusion?: string) =>
      d({ type: 'WORKER_UPDATE', worker_id, content, conclusion }),
    onInterrupt: (interrupt: InterruptInfo) =>
      d({ type: 'INTERRUPT', interrupt }),
    onComplete: (report: string) =>
      d({ type: 'COMPLETE', report }),
    onError: (message: string) =>
      d({ type: 'ERROR', message }),
    onToken: (content: string, node: string) =>
      d({ type: 'TOKEN', content, node }),
    onToolCall: (name: string, args: Record<string, unknown>, node: string) =>
      d({ type: 'TOOL_CALL', name, args, node }),
    onToolResult: (name: string, content: string, node: string) =>
      d({ type: 'TOOL_RESULT', name, content, node }),
  }
}

export function useInvestigation() {
  const [multi, dispatch] = useReducer(multiReducer, { investigations: {} })
  const { getAccessToken } = useAuth()
  const abortRefs = useRef<Map<string, AbortController>>(new Map())
  const sessionIdRefs = useRef<Map<string, string>>(new Map())

  const start = useCallback(async (scenarioName: string, incidentText?: string) => {
    try {
      const handlers = buildScopedHandlers(dispatch, scenarioName)

      if (isProductionMode) {
        const sessionId = crypto.randomUUID()
        sessionIdRefs.current.set(scenarioName, sessionId)

        dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'START', id: sessionId, scenarioName } })
        if (incidentText) {
          dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'MESSAGE', node: 'user', content: incidentText, role: 'human' } })
        }

        let incident = incidentText || ''
        if (!incidentText) {
          const scenario = await fetchScenario(scenarioName)
          incident = scenario.incident
        }

        const accessToken = await getAccessToken()
        const abort = await invokeAgentCore(
          { message: incident, scenario_name: scenarioName },
          sessionId,
          accessToken,
          handlers as AgentCoreStreamHandlers,
        )
        abortRefs.current.set(scenarioName, abort)
      } else {
        const id = await createInvestigation(scenarioName, incidentText)
        dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'START', id, scenarioName } })

        if (incidentText) {
          dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'MESSAGE', node: 'user', content: incidentText, role: 'human' } })
        }

        abortRefs.current.get(scenarioName)?.abort()
        const abort = await streamInvestigation(id, handlers)
        abortRefs.current.set(scenarioName, abort)
      }
    } catch (e) {
      dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'ERROR', message: (e as Error).message } })
    }
  }, [getAccessToken])

  const respond = useCallback(async (scenarioName: string, text: string) => {
    const inv = multi.investigations[scenarioName]
    if (!inv?.id) return
    try {
      dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'MESSAGE', node: 'user', content: text, role: 'human' } })
      dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'RESPOND' } })

      const handlers = buildScopedHandlers(dispatch, scenarioName)

      if (isProductionMode) {
        const sessionId = sessionIdRefs.current.get(scenarioName) ?? ''
        const accessToken = await getAccessToken()
        const abort = await invokeAgentCore(
          { message: text },
          sessionId,
          accessToken,
          handlers as AgentCoreStreamHandlers,
        )
        abortRefs.current.set(scenarioName, abort)
      } else {
        const abort = await streamInvestigation(inv.id, handlers, text)
        abortRefs.current.set(scenarioName, abort)
      }
    } catch (e) {
      dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'ERROR', message: (e as Error).message } })
    }
  }, [multi.investigations, getAccessToken])

  const stop = useCallback((scenarioName: string) => {
    abortRefs.current.get(scenarioName)?.abort()
    abortRefs.current.delete(scenarioName)
    dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'STOP' } })
  }, [])

  const reset = useCallback((scenarioName: string) => {
    abortRefs.current.get(scenarioName)?.abort()
    abortRefs.current.delete(scenarioName)
    sessionIdRefs.current.delete(scenarioName)
    dispatch({ type: 'DISPATCH', scenario: scenarioName, action: { type: 'RESET' } })
  }, [])

  return { investigations: multi.investigations, start, respond, stop, reset }
}

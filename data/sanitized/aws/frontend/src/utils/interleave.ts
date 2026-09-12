import type { StreamMessage, ToolCallInfo } from '../types/investigation'

export type InterleavedEntry =
  | { kind: 'message'; msg: StreamMessage; ts: number }
  | { kind: 'tool'; tc: ToolCallInfo; idx: number; ts: number }

/**
 * Merge messages and tool calls into a single chronologically sorted list.
 */
export function interleaveEntries(
  messages: StreamMessage[],
  toolCalls: ToolCallInfo[],
): InterleavedEntry[] {
  return [
    ...messages.map((msg) => ({ kind: 'message' as const, msg, ts: msg.timestamp })),
    ...toolCalls.map((tc, idx) => ({ kind: 'tool' as const, tc, idx, ts: tc.timestamp })),
  ].sort((a, b) => a.ts - b.ts)
}

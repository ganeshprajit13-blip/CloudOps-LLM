/**
 * Shared SSE stream reader for both FastAPI and AgentCore modes.
 *
 * Parses standard SSE wire format (data: {json}\n\n) from a fetch Response.
 * Used by both client.ts (local dev) and agentcore-client.ts (production).
 */

export interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

/**
 * Read SSE events from a fetch Response body.
 *
 * Expects the standard SSE wire format:
 *   data: {"event":"phase","data":{"phase":"clarification"}}\n\n
 *
 * Each parsed JSON object must have `event` (string) and `data` (object) fields.
 */
export async function readSSEStream(
  response: Response,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error('No response body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) break

      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Split on double-newline (SSE event boundary) or single newline for simple data: lines
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith(':')) continue // SSE comment or blank

        // Strip "data: " prefix
        const jsonStr = trimmed.startsWith('data: ') ? trimmed.slice(6) : trimmed.startsWith('data:') ? trimmed.slice(5) : null
        if (!jsonStr) continue

        try {
          const parsed = JSON.parse(jsonStr)
          if (parsed && typeof parsed.event === 'string' && parsed.data !== undefined) {
            onEvent(parsed as SSEEvent)
          }
        } catch {
          // Incomplete or malformed JSON — skip
        }
      }
    }

    // Process remaining buffer
    const trimmed = buffer.trim()
    if (trimmed) {
      const jsonStr = trimmed.startsWith('data: ') ? trimmed.slice(6) : trimmed.startsWith('data:') ? trimmed.slice(5) : null
      if (jsonStr) {
        try {
          const parsed = JSON.parse(jsonStr)
          if (parsed && typeof parsed.event === 'string' && parsed.data !== undefined) {
            onEvent(parsed as SSEEvent)
          }
        } catch {
          // ignore
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

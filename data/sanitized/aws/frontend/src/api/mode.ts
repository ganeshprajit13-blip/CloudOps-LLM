/**
 * Runtime mode detection for the frontend.
 *
 * Local dev (FastAPI):
 *   - VITE_AGENTCORE_ENDPOINT is empty
 *   - Scenarios fetched from /api/scenarios (FastAPI)
 *   - Investigations use fetch POST + SSE ReadableStream to FastAPI
 *
 * Production (AgentCore):
 *   - VITE_AGENTCORE_ENDPOINT is set to the AgentCore Runtime endpoint
 *   - Scenarios fetched from static /scenarios.json
 *   - Investigations use fetch POST + SSE ReadableStream to AgentCore
 */

export const AGENTCORE_ENDPOINT = import.meta.env.VITE_AGENTCORE_ENDPOINT || ''
export const isProductionMode = !!AGENTCORE_ENDPOINT

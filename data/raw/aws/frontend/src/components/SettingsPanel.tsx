import { useEffect, useState, useCallback } from 'react'
import { fetchConfigStatus, type ConfigStatus, type BackendStatus } from '../api/client'
import { isProductionMode } from '../api/mode'

interface SettingsPanelProps {
  onClose: () => void
}

// Human-readable labels for backend types
const TYPE_LABELS: Record<string, string> = {
  local: 'Local Files',
  athena: 'S3 + Athena',
  cloudwatch: 'CloudWatch Logs',
  opensearch: 'OpenSearch',
  bedrock_kb: 'Bedrock Knowledge Base',
  local_files: 'Local Files',
  memory: 'In-Memory',
  sqlite: 'SQLite',
  dynamodb: 'DynamoDB',
  agentcore_memory: 'AgentCore Memory',
  unconfigured: 'Not Configured',
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'ok' ? 'bg-green-500' : 'bg-red-500'
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
}

function StatusCard({ label, backend }: { label: string; backend: BackendStatus }) {
  const typeName = TYPE_LABELS[backend.type] || backend.type
  const details = backend.details || {}
  const detailEntries = Object.entries(details).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  )

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <div className="flex items-center gap-1.5">
          <StatusDot status={backend.status} />
          <span
            className={`text-[10px] font-medium ${backend.status === 'ok' ? 'text-green-700' : 'text-red-700'}`}
          >
            {backend.status === 'ok' ? 'Connected' : 'Error'}
          </span>
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-1">{typeName}</p>
      {backend.message && (
        <p className="text-[10px] text-red-600 mb-1">{backend.message}</p>
      )}
      {detailEntries.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {detailEntries.map(([key, value]) => (
            <div key={key} className="flex justify-between text-[10px]">
              <span className="text-gray-400">{key.replace(/_/g, ' ')}</span>
              <span className="text-gray-600 font-mono truncate ml-2 max-w-[200px]">
                {String(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [status, setStatus] = useState<ConfigStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchConfigStatus()
      if (data) {
        setStatus(data)
      } else if (isProductionMode) {
        setStatus(null)
      } else {
        setError('Unable to reach the backend API')
      }
    } catch {
      setError('Failed to fetch backend status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div className="w-[420px] flex-none border-l border-gray-200 bg-white flex flex-col h-full overflow-hidden animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-900">Backend Status</h2>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <span className="ml-2 text-xs text-gray-500">Checking backends...</span>
          </div>
        )}

        {!loading && error && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs text-amber-800">{error}</p>
          </div>
        )}

        {!loading && isProductionMode && !status && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-100 text-teal-700 uppercase tracking-wide">
                Production
              </span>
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600">
                Backends are managed by AWS CDK and AgentCore. Status is monitored
                via CloudWatch.
              </p>
            </div>
          </div>
        )}

        {!loading && status && (
          <>
            {/* Mode badge */}
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Agent
              </p>
              <div className="flex items-center gap-2">
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${
                    status.agent.mode === 'production'
                      ? 'bg-teal-100 text-teal-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}
                >
                  {status.agent.mode}
                </span>
                <span className="text-[10px] text-gray-400 font-mono">
                  {status.agent.region}
                </span>
              </div>
            </div>

            {/* Backend status cards */}
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Backends
              </p>
              <div className="space-y-2">
                <StatusCard label="Log Search" backend={status.backends.log_search} />
                <StatusCard label="Context Source" backend={status.backends.context_source} />
                <StatusCard label="Checkpoint" backend={status.backends.checkpoint} />
              </div>
            </div>

            {/* Refresh */}
            <div className="pt-1">
              <button
                onClick={refresh}
                disabled={loading}
                className="text-xs text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

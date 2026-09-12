import { useState } from 'react'

interface Props {
  onClose: () => void
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3.5">
      <div className="flex-none w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
        {n}
      </div>
      <div className="flex-1 min-w-0 pb-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-1.5">{title}</h3>
        {children}
      </div>
    </div>
  )
}

function Code({ children }: { children: string }) {
  return (
    <pre className="text-[11px] leading-relaxed bg-gray-900 text-gray-100 rounded-lg px-3.5 py-3 overflow-x-auto font-mono mt-2 mb-2">
      {children}
    </pre>
  )
}

function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2 mt-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
      <span className="text-amber-500 flex-none text-xs mt-px">Tip</span>
      <p className="text-[11px] text-amber-800 leading-relaxed">{children}</p>
    </div>
  )
}

export default function CreateScenarioGuide({ onClose }: Props) {
  const [treeOpen, setTreeOpen] = useState(false)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-none px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Create Your Own Scenario</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Add a directory under <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded border border-gray-200">scenarios/</code> and it appears in the picker automatically.{' '}
                <button
                  onClick={() => setTreeOpen(!treeOpen)}
                  className="text-blue-600 hover:text-blue-800 font-medium"
                >
                  {treeOpen ? 'Hide' : 'Show'} structure
                </button>
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-100 flex-none ml-4"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Collapsible directory tree */}
          {treeOpen && (
            <div className="mt-3 bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 font-mono text-[11px] text-gray-600 leading-relaxed">
              <div>scenarios/<span className="text-blue-600 font-semibold">my-scenario</span>/</div>
              <div className="pl-4">
                <div><span className="text-gray-400">├──</span> incident.md <span className="text-gray-400 text-[10px] ml-1">optional — for docs panel</span></div>
                <div><span className="text-gray-400">├──</span> ground_truth.yaml <span className="text-gray-400 text-[10px] ml-1">optional — for evaluation</span></div>
                <div><span className="text-gray-400">├──</span> context/</div>
                <div className="pl-6"><span className="text-gray-400">├──</span> runbooks.md</div>
                <div className="pl-6"><span className="text-gray-400">└──</span> past_incidents.md</div>
                <div><span className="text-gray-400">└──</span> evidence/</div>
                <div className="pl-6"><span className="text-gray-400">├──</span> service-a.log</div>
                <div className="pl-6"><span className="text-gray-400">└──</span> service-b.log</div>
              </div>
            </div>
          )}
        </div>

        {/* Steps */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <Step n={1} title="Write the incident report (optional)">
            <p className="text-xs text-gray-600 leading-relaxed">
              The agent starts from your <strong>user prompt</strong>, not this file. <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded border border-gray-200">incident.md</code> is shown in the <strong>docs panel</strong> to give reviewers context — skip it if you're investigating your own data.
            </p>
            <Tip>
              For <strong>HITL scenarios</strong>, keep it intentionally vague so the agent asks clarifying questions.
              For <strong>standard scenarios</strong>, include the time window, affected services, and symptoms.
            </Tip>
          </Step>

          <Step n={2} title="Add log files">
            <p className="text-xs text-gray-600 leading-relaxed">
              One <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded border border-gray-200">.log</code> file per service in <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded border border-gray-200">evidence/</code>. Use ISO timestamps so the agent can filter by time window.
            </p>
            <Code>{`2024-03-15T14:00:00.123Z INFO  payment-service [Pool] Healthy: 10/50 active
2024-03-15T14:01:00.456Z WARN  payment-service [Pool] Growing: 45/50 active
2024-03-15T14:01:30.789Z ERROR payment-service [Pool] Exhausted: 50/50 active`}</Code>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
              {['Mix INFO/WARN/ERROR realistically', 'Include red herrings & noise', 'Root cause appears before symptoms'].map((tip) => (
                <span key={tip} className="text-[10px] text-gray-400 flex items-center gap-1">
                  <span className="w-1 h-1 bg-gray-300 rounded-full" />
                  {tip}
                </span>
              ))}
            </div>
            <Tip>
              <strong>Have a lot of logs?</strong> Local mode reads flat files. For production-scale data, deploy with <strong>S3 + Athena</strong> (cheapest, ~$5/TB) or <strong>OpenSearch</strong> (fastest, sub-second search).
            </Tip>
          </Step>

          <Step n={3} title="Add context files">
            <p className="text-xs text-gray-600 leading-relaxed">
              The agent reads these before forming hypotheses. They provide domain knowledge and historical patterns.
            </p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-200">
                <div className="text-[11px] font-semibold text-gray-700">runbooks.md</div>
                <p className="text-[10px] text-gray-500 mt-0.5">Troubleshooting procedures, service architecture, known issues</p>
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-200">
                <div className="text-[11px] font-semibold text-gray-700">past_incidents.md</div>
                <p className="text-[10px] text-gray-500 mt-0.5">Historical incidents with root causes and resolutions</p>
              </div>
            </div>
            <Tip>
              <strong>Large knowledge corpus?</strong> Context retrieval uses <strong>Amazon Bedrock Knowledge Bases</strong> (hybrid search) in all modes. For hundreds of runbooks or years of incident history, ingest them into your Knowledge Base for semantic retrieval.
            </Tip>
          </Step>

          <Step n={4} title="Define the ground truth (optional)">
            <p className="text-xs text-gray-600 leading-relaxed">
              <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded border border-gray-200">ground_truth.yaml</code> powers the docs panel and defines the expected answer. Skip this if you're investigating your own data and don't know the root cause yet — the agent runs the same investigation either way.
            </p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">Standard</div>
                <Code>{`description: Cache failure scenario
difficulty: medium

root_cause:
  service: pricing-service
  issue: Cache TTL with no jitter
  details: All keys expired at once`}</Code>
              </div>
              <div>
                <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">HITL</div>
                <Code>{`hitl_scenario: true
hitl_clarification_type: time_dependent

hitl_flow:
  1_vague_report: "It's slow"
  2_clarification: "When?"
  3_user_response: "Thursday AM"
  5_correct_root_cause: "..."`}</Code>
              </div>
            </div>
          </Step>

          <Step n={5} title="Run it">
            <Code>{`python src/run_demo.py my-scenario`}</Code>
            <p className="text-xs text-gray-600">
              Or start the frontend and pick it from the scenario list.
            </p>
          </Step>
        </div>
      </div>
    </div>
  )
}

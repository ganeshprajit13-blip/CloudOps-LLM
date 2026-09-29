import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Bot, Sparkles, RefreshCw, AlertCircle, Server, Info, CheckCircle2 } from 'lucide-react';
import { troubleshootingApi } from '../api/troubleshootingApi';
import { resourceApi } from '../api/resourceApi';
import AIAnalysis from '../components/AIAnalysis';
import { AILoadingState } from '../components/LoadingState';
import { useLanguage } from '../context/LanguageContext';

export default function Troubleshooter() {
  const location = useLocation();
  const { t } = useLanguage();
  const [problem, setProblem] = useState(
    location.state?.problemText || 'Why is my website unreachable over HTTPS on port 443?'
  );
  const [ec2Instances, setEc2Instances] = useState([]);
  const [isResourcesLoading, setIsResourcesLoading] = useState(true);
  const [selectedResource, setSelectedResource] = useState('i-07243bdf548e18f5b');
  
  // Scoped resource telemetry state
  const [telemetryData, setTelemetryData] = useState(null);
  const [isTelemetryLoading, setIsTelemetryLoading] = useState(false);
  const [telemetryError, setTelemetryError] = useState(null);

  // Analysis state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const hasAnalyzedRef = useRef(false);

  // 1. Fetch available resources on mount
  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function loadInstances() {
      setIsResourcesLoading(true);
      try {
        const instances = await resourceApi.getCloudResources({ signal: controller.signal });
        if (active) {
          setEc2Instances(instances);
          if (instances && instances.length > 0) {
            const hasPreselected = instances.some(i => i.instanceId === selectedResource);
            if (!hasPreselected) {
              setSelectedResource(instances[0].instanceId);
            }
          }
        }
      } catch (err) {
        if (active && err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
          console.warn('Could not load EC2 list for dropdown:', err);
        }
      } finally {
        if (active) {
          setIsResourcesLoading(false);
        }
      }
    }
    loadInstances();

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  // 2. Fetch resource-specific telemetry when selectedResource changes
  const fetchResourceTelemetry = async (resourceId) => {
    if (!resourceId) {
      setTelemetryData(null);
      return;
    }

    setIsTelemetryLoading(true);
    setTelemetryError(null);

    try {
      const data = await resourceApi.getCloudContext(resourceId);
      setTelemetryData(data);
    } catch (err) {
      if (err?.name !== 'CanceledError' && err?.name !== 'AbortError') {
        console.warn(`Failed to fetch telemetry for ${resourceId}:`, err);
        setTelemetryError(err.message || 'Telemetry unavailable');
      }
    } finally {
      setIsTelemetryLoading(false);
    }
  };

  useEffect(() => {
    if (selectedResource) {
      fetchResourceTelemetry(selectedResource);
    }
  }, [selectedResource]);

  // 3. Handle Problem Analysis
  const handleAnalyze = async (textToAnalyze = problem) => {
    if (!textToAnalyze.trim() || isAnalyzing) return;
    setIsAnalyzing(true);
    setErrorMsg(null);

    try {
      const result = await troubleshootingApi.analyzeProblem(textToAnalyze, selectedResource || null);
      setAnalysisResult(result);
    } catch (err) {
      console.error('Troubleshooting error:', err);
      setErrorMsg(err.message || 'An error occurred during infrastructure diagnosis.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    if (location.state?.problemText && !hasAnalyzedRef.current) {
      hasAnalyzedRef.current = true;
      handleAnalyze(location.state.problemText);
    }
  }, [location.state]);

  // Helper to parse compact telemetry metrics
  const parseTelemetrySummary = () => {
    if (!telemetryData) return null;

    const resources = telemetryData.resources || {};
    const metrics = telemetryData.metrics || [];
    const hostTelemetry = resources.host_telemetry || [];
    const ec2List = resources.ec2 || [];

    // CPU
    let cpuText = 'Normal';
    const cpuMetric = metrics.find(m => m.metric_name === 'CPUUtilization');
    if (cpuMetric && cpuMetric.value !== undefined) {
      cpuText = `${cpuMetric.value}%`;
    } else if (ec2List[0]?.cpu_utilization) {
      cpuText = `${ec2List[0].cpu_utilization}%`;
    }

    // State
    const stateText = ec2List[0]?.state ? `${ec2List[0].state.charAt(0).toUpperCase() + ec2List[0].state.slice(1)}` : 'Running';

    // Services
    let servicesText = 'Normal';
    if (hostTelemetry.length > 0 && hostTelemetry[0].services) {
      const svcs = hostTelemetry[0].services;
      const runningCount = svcs.filter(s => strStatus(s.status) === 'running').length;
      const stopped = svcs.filter(s => strStatus(s.status) !== 'running');
      if (stopped.length > 0) {
        servicesText = stopped.map(s => `${s.name} (${s.status})`).join(', ');
      } else {
        servicesText = svcs.map(s => `${s.name} (${s.status})`).join(', ') || 'All Services Running';
      }
    }

    // Ports
    let portsText = '80, 3389 listening';
    if (hostTelemetry.length > 0 && hostTelemetry[0].listening_ports) {
      const ports = hostTelemetry[0].listening_ports.map(p => p.port).filter(Boolean);
      if (ports.length > 0) {
        portsText = `${ports.join(', ')} listening`;
      }
    }

    return {
      cpu: cpuText,
      state: stateText,
      services: servicesText,
      ports: portsText
    };
  };

  function strStatus(s) {
    return String(s || '').toLowerCase();
  }

  const parsedTelemetry = parseTelemetrySummary();

  return (
    <div className="space-y-8 animate-in fade-in duration-300 max-w-6xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-2 max-w-2xl mx-auto border-b border-slate-200 pb-4">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900 text-white border border-slate-800 text-xs font-bold uppercase tracking-wider shadow-2xs">
          <Bot className="w-4 h-4 text-white" />
          <span>{t('troubleshooterHeader')}</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
          {t('askAdvisor')}
        </h1>
      </div>

      {/* Interactive Input Box */}
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-xs space-y-5">
        
        {/* Resource Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <label className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-2">
            <Server className="w-4 h-4 text-slate-800" />
            <span>{t('selectResource')}</span>
          </label>

          <select
            value={selectedResource}
            onChange={(e) => setSelectedResource(e.target.value)}
            className="px-3.5 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-800 focus:outline-none focus:border-slate-900 transition-colors w-full sm:w-80 shadow-2xs"
          >
            {isResourcesLoading ? (
              <option disabled value="">Fetching resources...</option>
            ) : ec2Instances.length > 0 ? (
              ec2Instances.map((inst) => (
                <option key={inst.instanceId} value={inst.instanceId}>
                  {inst.displayLabel || `${inst.name || inst.instanceId} — ${inst.instanceId}`}
                </option>
              ))
            ) : (
              <option value="i-07243bdf548e18f5b">CloudOps-Test-Server — i-07243bdf548e18f5b</option>
            )}
          </select>
        </div>

        {/* Live Resource Telemetry Status Strip */}
        <div className="transition-all duration-200">
          {isTelemetryLoading && (
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-between text-xs text-slate-700 animate-pulse">
              <div className="flex items-center space-x-2">
                <RefreshCw className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                <span>Fetching telemetry for {selectedResource}...</span>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">Live AWS collector</span>
            </div>
          )}

          {telemetryError && !isTelemetryLoading && (
            <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-center justify-between text-xs font-medium">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Telemetry unavailable ({telemetryError})</span>
              </div>
              <button
                onClick={() => fetchResourceTelemetry(selectedResource)}
                className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold text-xs cursor-pointer transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {parsedTelemetry && !isTelemetryLoading && !telemetryError && (
            <div className="p-4 rounded-2xl bg-slate-50/90 border border-slate-200/80 space-y-2.5 text-xs animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="font-bold text-slate-900">Telemetry fetched</span>
                  <span className="text-slate-400">•</span>
                  <span className="font-mono text-slate-600 font-semibold">{selectedResource}</span>
                </div>
                <button
                  onClick={() => fetchResourceTelemetry(selectedResource)}
                  className="text-[11px] font-semibold text-blue-600 hover:underline flex items-center space-x-1 cursor-pointer"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Refresh</span>
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="p-2.5 rounded-xl bg-white border border-slate-200/70 shadow-2xs">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">CPU</span>
                  <span className="font-bold text-slate-900">{parsedTelemetry.cpu}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white border border-slate-200/70 shadow-2xs">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">State / OS</span>
                  <span className="font-bold text-slate-900">{parsedTelemetry.state}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white border border-slate-200/70 shadow-2xs">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">Services</span>
                  <span className="font-bold text-slate-900 truncate block" title={parsedTelemetry.services}>
                    {parsedTelemetry.services}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white border border-slate-200/70 shadow-2xs">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">Listening Ports</span>
                  <span className="font-bold text-slate-900 truncate block" title={parsedTelemetry.ports}>
                    {parsedTelemetry.ports}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Question Input */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
            {t('describeProblem')}
          </label>
          <div className="relative">
            <textarea
              rows={3}
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder={t('problemPlaceholder')}
              className="w-full p-4 rounded-2xl bg-gray-100 border border-gray-300 text-gray-900 text-sm placeholder-gray-500 focus:outline-none focus:border-black focus:bg-white transition-all resize-none font-medium shadow-2xs"
            />
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => handleAnalyze()}
            disabled={isAnalyzing || !problem.trim()}
            className="px-6 py-3.5 rounded-2xl bg-black hover:bg-zinc-900 text-white font-bold text-sm shadow-md transition-all flex items-center space-x-2 disabled:opacity-50 cursor-pointer"
          >
            {isAnalyzing ? (
              <RefreshCw className="w-4 h-4 animate-spin text-white" />
            ) : (
              <Sparkles className="w-4 h-4 text-white" />
            )}
            <span className="text-white font-bold">
              {isAnalyzing ? t('analyzing') : t('analyzeProblem')}
            </span>
          </button>
        </div>
      </div>

      {/* Error Banner State */}
      {errorMsg && (
        <div className="p-5 rounded-2xl bg-red-50 border border-red-200 text-red-800 flex items-start justify-between space-x-3 text-xs font-semibold animate-in fade-in">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-extrabold text-sm block">Analysis Request Failed</span>
              <p className="text-red-700 font-medium leading-relaxed">{errorMsg}</p>
            </div>
          </div>
          <button
            onClick={() => handleAnalyze()}
            className="px-3.5 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs shrink-0 cursor-pointer transition-colors"
          >
            Retry Analysis
          </button>
        </div>
      )}

      {/* SECTION-LEVEL TELEMETRY LOADING / RESULT DISPLAY */}
      <section className="space-y-4">
        {/* Subtle Refreshing Banner when refreshing existing data */}
        {isAnalyzing && analysisResult && (
          <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 flex items-center space-x-2 text-xs font-semibold animate-pulse">
            <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />
            <span>Refreshing cloud telemetry & AI diagnosis...</span>
          </div>
        )}

        {/* Section Loading Indicator when no previous data exists */}
        {isAnalyzing && !analysisResult && (
          <AILoadingState />
        )}

        {/* Empty State Banner */}
        {!isAnalyzing && !analysisResult && !errorMsg && (
          <div className="bg-white p-8 rounded-3xl border border-slate-200 text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 mx-auto flex items-center justify-center">
              <Info className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-extrabold text-slate-900">Ready for Infrastructure Analysis</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Select a target AWS resource, type your infrastructure question, and click <strong>Analyze Problem</strong> to run live telemetry evaluation and AI diagnosis.
            </p>
          </div>
        )}

        {/* Diagnosis Output Results */}
        {analysisResult && (
          <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-300">
            <AIAnalysis data={analysisResult} />
          </div>
        )}
      </section>
    </div>
  );
}


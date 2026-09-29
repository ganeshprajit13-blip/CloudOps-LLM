import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  Bot,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Zap,
  Clock,
  Server
} from 'lucide-react';
import { incidentApi } from '../api/incidentApi';
import { getSeverityBadgeClass, getStatusBadgeClass, formatDate } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingState';
import AIAnalysis from '../components/AIAnalysis';

export default function IncidentDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await incidentApi.getIncidentById(id);
        setIncident(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <LoadingSpinner message={`Loading Incident Details for ${id}...`} />;
  if (!incident) return <div className="p-8 text-center text-[#64748B]">Incident not found.</div>;

  const analysisData = {
    problem: incident.title,
    probableRootCause: incident.probableCause,
    confidence: incident.confidence || 92,
    evidence: incident.evidence || [],
    recommendedAction: incident.recommendedAction,
    impact: 'Application health checks failed. HTTPS clients experiencing port 443 timeout.',
    retrievedKnowledge: [
      {
        title: 'AWS Security Group & Port 443 Ingress Runbook',
        category: 'AWS Docs',
        relevance: '95%',
        snippet: 'Verify that the Security Group attached to your EC2 instance permits TCP port 443 from 0.0.0.0/0 or Load Balancer security group.'
      }
    ]
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <Link
          to="/incidents"
          className="inline-flex items-center space-x-2 text-xs font-semibold text-[#0369A1] hover:text-[#0284C7] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Incidents Table</span>
        </Link>

        <div className="flex items-center space-x-3">
          <Link
            to="/troubleshoot"
            state={{ problemText: incident.title }}
            className="px-4 py-2 rounded-xl bg-[#0284C7] hover:bg-[#0369A1] text-white text-xs font-bold shadow-xs transition-all flex items-center space-x-2 border border-[#0284C7]/20"
          >
            <Bot className="w-4 h-4" />
            <span>Ask AI Troubleshooter About This Incident</span>
          </Link>
        </div>
      </div>

      {/* Incident Summary Card */}
      <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[#E2E8F0] pb-4">
          <div>
            <div className="flex items-center space-x-3">
              <span className="font-mono text-sm font-bold text-[#0284C7]">{incident.id}</span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border uppercase tracking-wider ${getSeverityBadgeClass(incident.severity)}`}>
                {incident.severity} Severity
              </span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeClass(incident.status)}`}>
                {incident.status}
              </span>
            </div>
            <h1 className="text-xl lg:text-2xl font-bold text-[#0F172A] tracking-tight mt-2">
              {incident.title}
            </h1>
          </div>

          <div className="flex items-center space-x-4 text-xs text-[#64748B]">
            <div>
              <span className="block text-[10px] uppercase font-bold text-[#0369A1]">Service Component</span>
              <span className="font-semibold text-[#0F172A]">{incident.service}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase font-bold text-[#0369A1]">Detected Timestamp</span>
              <span className="font-semibold text-[#0F172A]">{formatDate(incident.detectedAt)}</span>
            </div>
          </div>
        </div>

        <p className="text-xs text-[#64748B] leading-relaxed">
          {incident.summary}
        </p>
      </div>

      {/* AI Root Cause, Confidence, Evidence & Recommendation Component */}
      <AIAnalysis data={analysisData} />
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Search,
  Filter,
  ArrowRight,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Sparkles
} from 'lucide-react';
import { incidentApi } from '../api/incidentApi';
import { getSeverityBadgeClass, getStatusBadgeClass, formatRelativeTime } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingState';
import { useLanguage } from '../context/LanguageContext';

export default function Incidents() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const { t } = useLanguage();

  useEffect(() => {
    async function load() {
      try {
        const data = await incidentApi.getIncidents();
        setIncidents(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <LoadingSpinner message="Fetching Active Cloud Incidents..." />;

  const filtered = incidents.filter((inc) => {
    if (severityFilter !== 'ALL' && inc.severity.toLowerCase() !== severityFilter.toLowerCase()) return false;
    if (statusFilter !== 'ALL' && inc.status.toLowerCase() !== statusFilter.toLowerCase()) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        inc.id.toLowerCase().includes(q) ||
        inc.title.toLowerCase().includes(q) ||
        inc.service.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
            {t('incidentsTitle')}
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Real-time AWS anomaly detections & AI root cause diagnoses
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="px-3 py-1 rounded-full bg-blue-50 text-blue-800 border border-blue-200 text-xs font-bold">
            {incidents.filter(i => i.severity === 'Critical').length} Critical
          </span>
          <span className="px-3 py-1 rounded-full bg-blue-100 text-blue-900 border border-blue-200 text-xs font-bold">
            {incidents.filter(i => i.status === 'Investigating').length} Investigating
          </span>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row gap-4 items-center justify-between">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder={t('searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 text-xs focus:outline-none focus:border-blue-600 font-medium"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs text-slate-700 font-bold">{t('severity')}:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 text-xs font-medium focus:outline-none"
            >
              <option value="ALL">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-700 font-bold">{t('status')}:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 text-xs font-medium focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="Investigating">Investigating</option>
              <option value="Identified">Identified</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 text-slate-700 uppercase tracking-wider font-bold border-b border-slate-200">
              <tr>
                <th className="px-6 py-4">Incident ID</th>
                <th className="px-6 py-4">Title & Details</th>
                <th className="px-6 py-4">{t('severity')}</th>
                <th className="px-6 py-4">Service</th>
                <th className="px-6 py-4">{t('status')}</th>
                <th className="px-6 py-4">{t('detectedAt')}</th>
                <th className="px-6 py-4">{t('aiConfidence')}</th>
                <th className="px-6 py-4 text-right">{t('action')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-slate-500 font-medium">
                    No matching cloud incidents found.
                  </td>
                </tr>
              ) : (
                filtered.map((inc) => (
                  <tr
                    key={inc.id}
                    className="hover:bg-blue-50/50 transition-colors group"
                  >
                    <td className="px-6 py-4 font-mono font-bold text-blue-700">
                      {inc.id}
                    </td>

                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {inc.title}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium truncate max-w-xs mt-0.5">
                        {inc.probableCause}
                      </div>
                    </td>

                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold border bg-blue-50 text-blue-800 border-blue-200 uppercase tracking-wider">
                        {inc.severity}
                      </span>
                    </td>

                    <td className="px-6 py-4 font-semibold text-slate-800">
                      {inc.service}
                    </td>

                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold border bg-slate-100 text-slate-800 border-slate-200">
                        {inc.status}
                      </span>
                    </td>

                    <td className="px-6 py-4 text-slate-600 font-medium whitespace-nowrap">
                      {formatRelativeTime(inc.detectedAt)}
                    </td>

                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <div className="w-12 bg-slate-100 rounded-full h-1.5 border border-slate-200">
                          <div
                            className="bg-blue-600 h-1.5 rounded-full"
                            style={{ width: `${inc.confidence}%` }}
                          />
                        </div>
                        <span className="font-bold text-blue-700">{inc.confidence}%</span>
                      </div>
                    </td>

                    <td className="px-6 py-4 text-right">
                      <Link
                        to={`/incident/${inc.id}`}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 font-bold transition-all"
                      >
                        <span>{t('investigate')}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

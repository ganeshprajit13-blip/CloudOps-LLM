import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Terminal,
  Search,
  Filter,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Clock,
  Download,
  AlertCircle,
  AlertTriangle,
  Info
} from 'lucide-react';
import { logsApi } from '../api/logsApi';
import { getLogLevelClass, formatDate } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingState';

export default function Logs() {
  const [searchParams] = useSearchParams();
  const initialSearch = searchParams.get('q') || '';

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialSearch);
  const [service, setService] = useState('ALL');
  const [level, setLevel] = useState('ALL');
  const [expandedLogId, setExpandedLogId] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    const q = searchParams.get('q');
    if (q) setSearch(q);
  }, [searchParams]);

  async function fetchLogs() {
    try {
      const res = await logsApi.getLogs({ service, level, search });
      setLogs(res.logs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs();
  }, [service, level, search]);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchLogs();
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, service, level, search]);

  const toggleExpand = (id) => {
    setExpandedLogId(expandedLogId === id ? null : id);
  };

  const getLevelIcon = (lvl) => {
    switch (lvl) {
      case 'ERROR':
        return <AlertCircle className="w-3.5 h-3.5 text-rose-600" />;
      case 'WARNING':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />;
      default:
        return <Info className="w-3.5 h-3.5 text-[#0284C7]" />;
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
              CloudWatch & System Logs
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-xs font-semibold shrink-0">
              Live Log Stream
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] font-normal">
            Real-time aggregated AWS log stream & error event inspector
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3.5 py-2 rounded-xl border text-xs font-semibold transition-all flex items-center space-x-2 ${
              autoRefresh
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 shadow-xs'
                : 'bg-white text-[#0F172A] border-[#E2E8F0] hover:bg-[#F0F7FF]'
            }`}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${autoRefresh ? 'animate-spin text-emerald-600' : 'text-[#0369A1]'}`} />
            <span>{autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 sm:p-5 rounded-2xl border border-[#E2E8F0] shadow-xs flex flex-col md:flex-row gap-4 items-center justify-between">
        {/* Search */}
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0369A1]" />
          <input
            type="text"
            placeholder="Search log messages, IP addresses, trace IDs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] placeholder-[#0369A1]/60 focus:outline-none focus:border-[#0284C7] font-mono text-xs font-medium"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto justify-end text-xs">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-[#64748B]">Service:</span>
            <select
              value={service}
              onChange={(e) => setService(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] font-semibold focus:outline-none"
            >
              <option value="ALL">All Services</option>
              <option value="EC2">EC2</option>
              <option value="ALB">ALB</option>
              <option value="CloudWatch">CloudWatch</option>
              <option value="RDS">RDS</option>
              <option value="VPC">VPC Flow Logs</option>
              <option value="Lambda">Lambda</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="font-semibold text-[#64748B]">Severity:</span>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] font-semibold focus:outline-none"
            >
              <option value="ALL">All Levels</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
            </select>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      {loading ? (
        <LoadingSpinner message="Fetching live CloudWatch log streams..." />
      ) : (
        <div className="bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-xs font-mono text-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                <tr>
                  <th className="px-4 py-3.5 w-8"></th>
                  <th className="px-4 py-3.5">Timestamp</th>
                  <th className="px-4 py-3.5">Service</th>
                  <th className="px-4 py-3.5">Level</th>
                  <th className="px-6 py-3.5">Log Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-[#64748B] font-sans">
                      No log entries match the current filter criteria.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => {
                    const isExpanded = expandedLogId === log.id;
                    return (
                      <React.Fragment key={log.id}>
                        <tr
                          onClick={() => toggleExpand(log.id)}
                          className="hover:bg-[#F8FAFC] cursor-pointer transition-colors"
                        >
                          <td className="px-4 py-3.5 text-[#64748B]">
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </td>

                          <td className="px-4 py-3.5 text-[#64748B] whitespace-nowrap">
                            {formatDate(log.timestamp)}
                          </td>

                          <td className="px-4 py-3.5">
                            <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] border border-[#BAE6FD] text-[#0284C7] font-semibold text-[11px]">
                              {log.service}
                            </span>
                          </td>

                          <td className="px-4 py-3.5">
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border flex items-center space-x-1 w-fit ${getLogLevelClass(log.level)}`}>
                              {getLevelIcon(log.level)}
                              <span>{log.level}</span>
                            </span>
                          </td>

                          <td className="px-6 py-3.5 text-[#0F172A] font-sans font-medium truncate max-w-lg">
                            {log.message}
                          </td>
                        </tr>

                        {/* Expanded JSON Detail Row */}
                        {isExpanded && (
                          <tr className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                            <td></td>
                            <td colSpan={4} className="p-4">
                              <div className="space-y-2">
                                <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                                  <span className="font-bold text-[#0284C7] uppercase">Raw Log Event Payload</span>
                                  <span>Event ID: {log.id}</span>
                                </div>
                                <pre className="p-4 rounded-xl bg-white border border-[#E2E8F0] text-[#0F172A] text-xs overflow-x-auto font-mono shadow-xs">
                                  {JSON.stringify(JSON.parse(log.rawJson || '{}'), null, 2)}
                                </pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

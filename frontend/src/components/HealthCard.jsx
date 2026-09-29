import React from 'react';

export default function HealthCard({ title, value, status, icon: Icon, description, trend, loading = false }) {
  if (loading) {
    return (
      <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/90 shadow-xs flex flex-col justify-between h-full animate-pulse">
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="h-3 w-24 bg-slate-200 rounded" />
            <div className="w-8 h-8 rounded-xl bg-slate-100" />
          </div>
          <div className="flex items-baseline justify-between gap-2 mt-3">
            <div className="h-8 w-24 bg-slate-200 rounded-lg" />
            <div className="h-5 w-16 bg-slate-100 rounded-full" />
          </div>
        </div>
        <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
          <div className="h-3 w-32 bg-slate-100 rounded" />
          <div className="h-3 w-10 bg-slate-100 rounded" />
        </div>
      </div>
    );
  }

  const getStatusBadge = (st) => {
    switch (st?.toLowerCase()) {
      case 'healthy':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200/80';
      case 'warning':
        return 'bg-amber-50 text-amber-700 border-amber-200/80';
      case 'critical':
        return 'bg-rose-50 text-rose-700 border-rose-200/80';
      default:
        return 'bg-[#E0F2FE] text-[#0284C7] border-[#BAE6FD]';
    }
  };

  return (
    <div className="bg-white p-5 sm:p-6 rounded-2xl border border-[#E2E8F0] hover:border-[#BAE6FD] transition-all duration-200 shadow-xs flex flex-col justify-between h-full group">
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#0369A1]">{title}</span>
          {Icon && (
            <div className="w-8 h-8 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD]/80 flex items-center justify-center text-[#0284C7] shrink-0">
              <Icon className="w-4 h-4" />
            </div>
          )}
        </div>

        <div className="flex items-baseline justify-between gap-2 mt-1">
          <h3 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight leading-none">{value}</h3>
          {status && (
            <span className={`px-2.5 py-0.5 text-[11px] font-semibold rounded-full border uppercase tracking-wider shrink-0 ${getStatusBadge(status)}`}>
              {status}
            </span>
          )}
        </div>
      </div>

      {description && (
        <div className="mt-5 pt-3 border-t border-[#E2E8F0] flex items-center justify-between text-xs text-[#64748B]">
          <span className="font-normal truncate">{description}</span>
          {trend && (
            <span
              className={`font-semibold shrink-0 ml-2 ${
                status?.toLowerCase() === 'critical'
                  ? 'text-rose-600'
                  : status?.toLowerCase() === 'warning'
                  ? 'text-amber-600'
                  : 'text-[#0284C7]'
              }`}
            >
              {trend}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// Formatting utilities for CloudOps LLM

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
};

export const formatRelativeTime = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now - date) / 1000);

  if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  return `${Math.floor(diffInSeconds / 86400)}d ago`;
};

export const getSeverityBadgeClass = (severity) => {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return 'bg-red-500/10 text-red-400 border-red-500/30';
    case 'high':
      return 'bg-orange-500/10 text-orange-400 border-orange-500/30';
    case 'medium':
      return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    default:
      return 'bg-gray-500/10 text-gray-400 border-gray-500/30';
  }
};

export const getStatusBadgeClass = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy':
    case 'resolved':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    case 'warning':
    case 'investigating':
    case 'identified':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    case 'critical':
    case 'unhealthy':
    case 'stopped':
    case 'error':
      return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    default:
      return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
  }
};

export const getLogLevelClass = (level) => {
  switch (level?.toUpperCase()) {
    case 'ERROR':
    case 'CRITICAL':
    case 'FATAL':
      return 'bg-red-950/60 text-red-400 border-red-800/50';
    case 'WARN':
    case 'WARNING':
      return 'bg-amber-950/60 text-amber-400 border-amber-800/50';
    case 'INFO':
      return 'bg-blue-950/60 text-blue-400 border-blue-800/50';
    default:
      return 'bg-gray-900/60 text-gray-400 border-gray-800/50';
  }
};

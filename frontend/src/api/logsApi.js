import api from './axios';
import { mockLogs } from './mockData';

export const logsApi = {
  getLogs: async (filters = {}) => {
    try {
      const response = await api.get('/api/logs', { params: filters });
      return response.data;
    } catch (error) {
      console.warn('Backend /api/logs unavailable. Returning mock log stream.');
      let logs = [...mockLogs];

      if (filters.service && filters.service !== 'ALL') {
        logs = logs.filter(l => l.service.toLowerCase() === filters.service.toLowerCase());
      }
      if (filters.level && filters.level !== 'ALL') {
        logs = logs.filter(l => l.level.toUpperCase() === filters.level.toUpperCase());
      }
      if (filters.search) {
        const q = filters.search.toLowerCase();
        logs = logs.filter(l => l.message.toLowerCase().includes(q) || l.service.toLowerCase().includes(q));
      }

      return {
        logs,
        total: logs.length,
        page: 1,
        pageSize: 10
      };
    }
  }
};

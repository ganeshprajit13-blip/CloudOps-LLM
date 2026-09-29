import api from './axios';
import { mockIncidents } from './mockData';

export const incidentApi = {
  getIncidents: async () => {
    try {
      const response = await api.get('/api/incidents');
      if (Array.isArray(response.data)) return response.data;
      if (Array.isArray(response.data?.incidents)) return response.data.incidents;
      return mockIncidents;
    } catch (error) {
      console.warn('Backend /api/incidents unavailable. Returning mock incidents.');
      return mockIncidents;
    }
  },

  getIncidentById: async (id) => {
    try {
      const response = await api.get(`/api/incidents/${id}`);
      return response.data;
    } catch (error) {
      console.warn(`Backend /api/incidents/${id} unavailable. Returning fallback incident.`);
      const found = mockIncidents.find((inc) => inc.id === id);
      return found || mockIncidents[0];
    }
  },

  updateIncidentStatus: async (id, status) => {
    try {
      const response = await api.patch(`/api/incidents/${id}`, { status });
      return response.data;
    } catch (error) {
      const found = mockIncidents.find((inc) => inc.id === id);
      if (found) found.status = status;
      return { success: true, id, status };
    }
  }
};

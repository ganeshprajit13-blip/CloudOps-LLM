import api from './axios';
import { mockKnowledgeBase } from './mockData';

export const knowledgeApi = {
  getKnowledgeBase: async () => {
    try {
      const response = await api.get('/api/knowledge');
      return response.data;
    } catch (error) {
      console.warn('Backend /api/knowledge unavailable. Trying /api/rag/knowledge or fallback.');
      try {
        const res2 = await api.get('/api/rag/knowledge');
        return res2.data;
      } catch (err2) {
        return mockKnowledgeBase;
      }
    }
  },

  searchKnowledgeBase: async (query) => {
    try {
      const response = await api.get(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
      return response.data;
    } catch (error) {
      const q = (query || '').toLowerCase();
      return mockKnowledgeBase.filter(item =>
        item.title.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q)
      );
    }
  },

  getChunkDetails: async (docId) => {
    try {
      const response = await api.get(`/api/knowledge/${docId}`);
      return response.data;
    } catch (error) {
      return mockKnowledgeBase.find(item => item.id === docId);
    }
  }
};

import api from './axios';

export const supportApi = {
  chat: async (message, history = [], rcaContext = null) => {
    try {
      const response = await api.post('/api/support-chat', {
        message,
        history,
        rca_context: rcaContext
      });
      return response.data;
    } catch (error) {
      console.warn('Backend Support Agent endpoint failed:', error);
      throw error;
    }
  }
};

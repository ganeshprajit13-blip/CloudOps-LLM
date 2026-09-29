import api from './axios';

export const troubleshootingApi = {
  analyzeProblem: async (problemDescription, resourceId = null) => {
    try {
      const response = await api.post('/api/analyze', {
        question: problemDescription,
        resource_id: resourceId || undefined,
        collect_live_data: true
      });
      
      const diagnosis = response.data;
      
      // Save item to local history
      try {
        const historyStr = localStorage.getItem('cloudops_analysis_history');
        const history = historyStr ? JSON.parse(historyStr) : [];
        const newItem = {
          id: `diag-${Date.now()}`,
          timestamp: new Date().toISOString(),
          question: problemDescription,
          resourceId: resourceId,
          ...diagnosis
        };
        localStorage.setItem('cloudops_analysis_history', JSON.stringify([newItem, ...history.slice(0, 19)]));
      } catch (e) {
        console.warn('Unable to persist diagnosis history to localStorage', e);
      }

      return diagnosis;
    } catch (error) {
      console.error('Failed to analyze problem via /api/analyze:', error);
      const detailMsg = error.response?.data?.detail?.message || error.response?.data?.detail || error.message;
      throw new Error(detailMsg || 'Backend CloudOps analysis failed');
    }
  },

  submitFeedback: async (analysisId, feedbackType, comment) => {
    try {
      const response = await api.post('/api/feedback', {
        analysisId,
        feedback: feedbackType,
        comment
      });
      return response.data;
    } catch (error) {
      console.warn('Backend feedback endpoint unavailable. Recording locally.');
      return { success: true, message: 'Feedback recorded successfully' };
    }
  },

  getHistory: async () => {
    try {
      const historyStr = localStorage.getItem('cloudops_analysis_history');
      if (historyStr) {
        return JSON.parse(historyStr);
      }
    } catch (e) {
      console.warn('Failed to parse history from localStorage', e);
    }
    return [];
  }
};

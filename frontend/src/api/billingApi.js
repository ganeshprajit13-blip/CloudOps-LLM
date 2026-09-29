import api from './axios';
import { mockBillingData } from './mockData';

export const billingApi = {
  getBillingData: async () => {
    try {
      const response = await api.get('/api/billing');
      return response.data;
    } catch (error) {
      console.warn('Backend /api/billing unavailable. Returning mock AWS billing data.');
      return mockBillingData;
    }
  }
};

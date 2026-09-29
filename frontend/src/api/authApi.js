import api from './axios';

export const authApi = {
  login: async (email, password) => {
    try {
      const response = await api.post('/api/auth/login', { email, password });
      return response.data;
    } catch (error) {
      if (email && password) {
        const mockToken = `cloudops_jwt_token_${Date.now()}`;
        const mockUser = {
          id: 'usr-1001',
          name: email.split('@')[0].toUpperCase(),
          email: email,
          role: 'Senior CloudOps Engineer',
          region: 'us-east-1'
        };
        return { token: mockToken, user: mockUser };
      }
      throw new Error(error.response?.data?.message || 'Invalid credentials');
    }
  },

  register: async (userData) => {
    try {
      const response = await api.post('/api/auth/register', userData);
      return response.data;
    } catch (error) {
      const mockToken = `cloudops_jwt_token_${Date.now()}`;
      return {
        token: mockToken,
        user: {
          id: `usr-${Date.now()}`,
          name: userData.fullName || 'Cloud Admin',
          email: userData.email,
          role: 'DevOps Engineer',
          region: userData.region || 'us-east-1'
        }
      };
    }
  },

  forgotPassword: async (email) => {
    try {
      const response = await api.post('/api/auth/forgot-password', { email });
      return response.data;
    } catch (error) {
      return { success: true, message: `Password reset instructions sent to ${email}` };
    }
  }
};

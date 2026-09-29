import axios from 'axios';

// Get base URL from env or dynamic user settings override in localStorage
export const getApiBaseUrl = () => {
  const customUrl = localStorage.getItem('cloudops_api_base_url');
  if (customUrl) return customUrl;
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach JWT auth token
api.interceptors.request.use(
  (config) => {
    config.baseURL = getApiBaseUrl();
    const token = localStorage.getItem('cloudops_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle API errors gracefully
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED' || error.message.includes('Network Error')) {
      console.warn('FastAPI Backend unavailable. Triggering fallback dataset.');
    }
    return Promise.reject(error);
  }
);

export default api;

import axios from 'axios';
import Cookies from 'js-cookie';

// Dynamic base URL with protocol detection
const getApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Client-side: use the same protocol as the current page
    const protocol = window.location.protocol.slice(0, -1); // Remove ':' from 'https:'
    const host = window.location.hostname;
    return `${protocol}://${host}`;
  }

  // Server-side: use environment variable or default to localhost
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'localhost';
  const protocol = process.env.NODE_ENV === 'production' ? 'https' : 'http';
  return `${protocol}://${baseUrl}`;
};

const axiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
axiosInstance.interceptors.request.use(
  (config) => {
    const token = Cookies.get('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = Cookies.get('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${getApiBaseUrl()}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token } = response.data;
          Cookies.set('access_token', access_token, { expires: 7 });

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return axiosInstance(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        Cookies.remove('access_token');
        Cookies.remove('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const apiClient = {
  get: async <T = any>(url: string, config?: any): Promise<T> => {
    const response = await axiosInstance.get(url, config);
    return response.data;
  },

  post: async <T = any>(url: string, data?: any, config?: any): Promise<T> => {
    const response = await axiosInstance.post(url, data, config);
    return response.data;
  },

  put: async <T = any>(url: string, data?: any, config?: any): Promise<T> => {
    const response = await axiosInstance.put(url, data, config);
    return response.data;
  },

  delete: async <T = any>(url: string, config?: any): Promise<T> => {
    const response = await axiosInstance.delete(url, config);
    return response.data;
  },

  patch: async <T = any>(url: string, data?: any, config?: any): Promise<T> => {
    const response = await axiosInstance.patch(url, data, config);
    return response.data;
  },
};

// Chatbot specific API methods
export const chatbotApi = {
  create: async (data: any) => apiClient.post('/api/chatbot/create', data),
  list: async () => apiClient.get('/api/chatbot/list'),
  update: async (id: string, data: any) => apiClient.put(`/api/chatbot/update/${id}`, data),
  delete: async (id: string) => apiClient.delete(`/api/chatbot/delete/${id}`),
  chat: async (id: string, message: string, config?: any) =>
    apiClient.post(`/api/chatbot/chat`, { chatbot_id: id, message, ...config }),
};
'use client';

import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to attach auth token
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('hra_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Add response interceptor to handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('hra_access_token');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export default apiClient;

// API Functions
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/auth/login', { email, password }),
  me: () => apiClient.get('/auth/me'),
};

export const positionsApi = {
  list: (status?: string) =>
    apiClient.get('/positions', { params: { status } }),
  create: (data: any) => apiClient.post('/positions', data),
  getById: (id: string) => apiClient.get(`/positions/${id}`),
  update: (id: string, data: any) => apiClient.patch(`/positions/${id}`, data),
};

export const criteriaApi = {
  listVersions: (positionId: string) =>
    apiClient.get(`/criteria/position/${positionId}/versions`),
  getById: (id: string) => apiClient.get(`/criteria/${id}`),
  generateDraft: (positionId: string) =>
    apiClient.post(`/criteria/generate/${positionId}`),
  approve: (id: string, action: 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES', comment?: string) =>
    apiClient.post(`/criteria/${id}/approve`, { action, comment }),
  getApproved: (positionId: string) =>
    apiClient.get(`/criteria/position/${positionId}/approved`),
};

export const applicationsApi = {
  uploadBatch: (positionId: string, files: File[], onProgress?: (percent: number) => void) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return apiClient.post(`/applications/upload-batch/${positionId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      },
    });
  },
  list: (positionId: string, params?: any) =>
    apiClient.get('/applications', { params: { position_id: positionId, ...params } }),
  getById: (id: string) => apiClient.get(`/applications/${id}`),
  updateStatus: (id: string, newStatus: string, reason?: string, note?: string) =>
    apiClient.patch(`/applications/${id}/status`, { new_status: newStatus, reason, note }),
  getCvUrl: (id: string) => apiClient.get(`/applications/${id}/cv-download-url`),
};

export const operationsApi = {
  getStatus: (id: string) => apiClient.get(`/operations/${id}`),
};

export const assessmentsApi = {
  runForPosition: (positionId: string) =>
    apiClient.post(`/assessments/run/${positionId}`),
  getById: (id: string) => apiClient.get(`/assessments/${id}`),
  generateRanking: (positionId: string) =>
    apiClient.post(`/assessments/ranking/generate/${positionId}`),
  getLatestRanking: (positionId: string) =>
    apiClient.get(`/assessments/ranking/latest/${positionId}`),
};

export const shortlistApi = {
  create: (data: any) => apiClient.post('/shortlist/share', data),
  getSharedWithMe: () => apiClient.get('/shortlist/shared-with-me'),
  getDetail: (id: string) => apiClient.get(`/shortlist/${id}`),
  addFeedback: (id: string, content: string, applicationId?: string) =>
    apiClient.post(`/shortlist/${id}/feedback`, { content, application_id: applicationId }),
  revoke: (id: string) => apiClient.post(`/shortlist/${id}/revoke`),
};

export const dashboardApi = {
  getSummary: () => apiClient.get('/dashboard/summary'),
  getPosition: (id: string) => apiClient.get(`/dashboard/position/${id}`),
};

export const adminApi = {
  listAiConfigs: () => apiClient.get('/admin/ai/config'),
  createAiConfig: (data: any) => apiClient.post('/admin/ai/config', data),
  enableAiConfig: (id: string) => apiClient.post(`/admin/ai/config/${id}/enable`),
  getActiveAiConfig: () => apiClient.get('/admin/ai/active-config'),
};

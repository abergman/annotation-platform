export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  // Auth endpoints
  AUTH: {
    REGISTER: '/api/auth/register',
    LOGIN: '/api/auth/login',
    LOGOUT: '/api/auth/logout',
    ME: '/api/auth/me',
    UPDATE_PROFILE: '/api/auth/me',
  },
  // Project endpoints
  PROJECTS: {
    BASE: '/api/projects',
    BY_ID: (id: number) => `/api/projects/${id}`,
  },
  // Text endpoints
  TEXTS: {
    BASE: '/api/texts',
    BY_ID: (id: number) => `/api/texts/${id}`,
    UPLOAD: '/api/texts/upload',
  },
  // Annotation endpoints
  ANNOTATIONS: {
    BASE: '/api/annotations',
    BY_ID: (id: number) => `/api/annotations/${id}`,
    VALIDATE: (id: number) => `/api/annotations/${id}/validate`,
  },
  // Label endpoints
  LABELS: {
    BASE: '/api/labels',
    BY_ID: (id: number) => `/api/labels/${id}`,
    HIERARCHY: (projectId: number) => `/api/labels/project/${projectId}/hierarchy`,
  },
  // Export endpoints
  EXPORT: {
    ANNOTATIONS: '/api/export/annotations',
    PROJECT_SUMMARY: (id: number) => `/api/export/project/${id}/summary`,
  },
};

export const LOCAL_STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  USER_PREFERENCES: 'user_preferences',
  SELECTED_PROJECT: 'selected_project',
};

export const VALIDATION_RULES = {
  PASSWORD_MIN_LENGTH: 8,
  USERNAME_MIN_LENGTH: 3,
  PROJECT_NAME_MAX_LENGTH: 200,
  LABEL_NAME_MAX_LENGTH: 100,
};

export const SUPPORTED_FILE_TYPES = [
  '.txt',
  '.pdf',
  '.docx',
  '.doc',
  '.rtf',
];

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export const DEFAULT_COLORS = [
  '#3b82f6', // blue-500
  '#ef4444', // red-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
  '#84cc16', // lime-500
  '#ec4899', // pink-500
  '#6b7280', // gray-500
];

export const ANNOTATION_VALIDATION_STATUS = {
  PENDING: 'pending' as const,
  APPROVED: 'approved' as const,
  REJECTED: 'rejected' as const,
};

export const USER_ROLES = {
  ADMIN: 'admin',
  RESEARCHER: 'researcher',
  ANNOTATOR: 'annotator',
};

export const EXPORT_FORMATS = [
  { value: 'json', label: 'JSON', extension: '.json' },
  { value: 'csv', label: 'CSV', extension: '.csv' },
  { value: 'xlsx', label: 'Excel', extension: '.xlsx' },
  { value: 'xml', label: 'XML', extension: '.xml' },
];
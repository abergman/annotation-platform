// API Types for Project Management Interface
export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  status: 'active' | 'completed' | 'archived';
  texts_count: number;
  annotations_count: number;
  members_count: number;
  settings: ProjectSettings;
}

export interface ProjectSettings {
  allow_overlapping_annotations: boolean;
  require_label_validation: boolean;
  auto_save_interval: number;
  annotation_guidelines?: string;
  label_schema: LabelSchema;
}

export interface LabelSchema {
  id: string;
  name: string;
  labels: Label[];
}

export interface Label {
  id: string;
  name: string;
  color: string;
  description?: string;
  parent_id?: string;
  children?: Label[];
  shortcut_key?: string;
}

export interface Text {
  id: string;
  title: string;
  content: string;
  project_id: string;
  uploaded_at: string;
  uploaded_by: string;
  status: 'processing' | 'ready' | 'annotating' | 'completed';
  annotations_count: number;
  file_name: string;
  file_size: number;
  metadata?: Record<string, any>;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role: 'admin' | 'manager' | 'annotator' | 'viewer';
  created_at: string;
  last_login?: string;
  is_active: boolean;
}

export interface ProjectMember {
  id: string;
  user: User;
  project_id: string;
  role: 'owner' | 'manager' | 'annotator' | 'viewer';
  added_at: string;
  added_by: string;
  permissions: string[];
}

export interface Annotation {
  id: string;
  text_id: string;
  user_id: string;
  start_offset: number;
  end_offset: number;
  selected_text: string;
  label: Label;
  confidence?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ExportOptions {
  format: 'json' | 'csv' | 'xml' | 'conll';
  include_metadata: boolean;
  include_confidence: boolean;
  include_notes: boolean;
  filter_by_user?: string[];
  filter_by_label?: string[];
  date_range?: {
    start: string;
    end: string;
  };
}

export interface ExportJob {
  id: string;
  project_id: string;
  created_by: string;
  options: ExportOptions;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  completed_at?: string;
  download_url?: string;
  error_message?: string;
}

export interface UploadProgress {
  id: string;
  file_name: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error_message?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
  pagination?: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
  };
}

export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, any>;
}

// Filter and Search Types
export interface ProjectFilter {
  status?: string[];
  created_by?: string[];
  date_range?: {
    start: string;
    end: string;
  };
  has_texts?: boolean;
}

export interface TextFilter {
  status?: string[];
  uploaded_by?: string[];
  date_range?: {
    start: string;
    end: string;
  };
}

export interface UserFilter {
  role?: string[];
  is_active?: boolean;
  last_login_range?: {
    start: string;
    end: string;
  };
}

export interface SearchOptions {
  query: string;
  fields?: string[];
  exact_match?: boolean;
}

export interface SortOptions {
  field: string;
  direction: 'asc' | 'desc';
}

export interface PaginationOptions {
  page: number;
  per_page: number;
}
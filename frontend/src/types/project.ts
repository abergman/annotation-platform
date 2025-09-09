export interface Project {
  id: number;
  name: string;
  description?: string;
  annotation_guidelines?: string;
  allow_multiple_labels: boolean;
  require_all_texts: boolean;
  inter_annotator_agreement: boolean;
  is_active: boolean;
  is_public: boolean;
  created_at?: string;
  updated_at?: string;
  owner_id: number;
  text_count: number;
  label_count: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  annotation_guidelines?: string;
  allow_multiple_labels?: boolean;
  require_all_texts?: boolean;
  inter_annotator_agreement?: boolean;
  is_public?: boolean;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  annotation_guidelines?: string;
  allow_multiple_labels?: boolean;
  require_all_texts?: boolean;
  inter_annotator_agreement?: boolean;
  is_public?: boolean;
  is_active?: boolean;
}

export interface Text {
  id: number;
  title: string;
  content?: string;
  original_filename?: string;
  file_type?: string;
  file_size?: number;
  language: string;
  word_count?: number;
  character_count?: number;
  metadata?: Record<string, any>;
  is_processed: string;
  processing_notes?: string;
  created_at?: string;
  updated_at?: string;
  project_id: number;
  annotation_count: number;
}

export interface TextCreate {
  title: string;
  content: string;
  project_id: number;
  language?: string;
  metadata?: Record<string, any>;
}

export interface TextUpdate {
  title?: string;
  content?: string;
  language?: string;
  metadata?: Record<string, any>;
}
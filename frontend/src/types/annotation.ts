export interface Annotation {
  id: string;
  textId: string;
  startOffset: number;
  endOffset: number;
  text: string;
  labels: string[];
  confidence?: number;
  notes?: string;
  createdAt: Date;
  updatedAt: Date;
  createdBy: string;
  status: 'draft' | 'pending' | 'validated' | 'rejected';
}

export interface Label {
  id: string;
  name: string;
  color: string;
  description?: string;
  shortcut?: string;
}

export interface TextSpan {
  startOffset: number;
  endOffset: number;
  text: string;
}

export interface AnnotationProject {
  id: string;
  name: string;
  description?: string;
  labels: Label[];
  texts: TextDocument[];
  createdAt: Date;
  updatedAt: Date;
}

export interface TextDocument {
  id: string;
  title: string;
  content: string;
  metadata?: Record<string, any>;
  annotations: Annotation[];
}

export interface AnnotationFilter {
  labels?: string[];
  status?: Annotation['status'][];
  confidence?: { min?: number; max?: number };
  createdBy?: string[];
  dateRange?: { start?: Date; end?: Date };
}

export interface SelectionRange {
  startContainer: Node;
  endContainer: Node;
  startOffset: number;
  endOffset: number;
  text: string;
}
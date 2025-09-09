import { apiService } from './api';
import { API_ENDPOINTS } from '@/utils/constants';
import { 
  Project, 
  ProjectCreate, 
  ProjectUpdate,
  Text,
  TextCreate,
  TextUpdate,
} from '@/types/project';
import { QueryParams } from '@/types/api';

export class ProjectService {
  /**
   * Create a new project
   */
  async create(projectData: ProjectCreate): Promise<Project> {
    return apiService.post<Project>(API_ENDPOINTS.PROJECTS.BASE, projectData);
  }

  /**
   * Get list of projects with optional filters
   */
  async list(params?: QueryParams & {
    owner_only?: boolean;
  }): Promise<Project[]> {
    return apiService.get<Project[]>(API_ENDPOINTS.PROJECTS.BASE, params);
  }

  /**
   * Get a specific project by ID
   */
  async getById(id: number): Promise<Project> {
    return apiService.get<Project>(API_ENDPOINTS.PROJECTS.BY_ID(id));
  }

  /**
   * Update a project
   */
  async update(id: number, projectData: ProjectUpdate): Promise<Project> {
    return apiService.put<Project>(
      API_ENDPOINTS.PROJECTS.BY_ID(id), 
      projectData
    );
  }

  /**
   * Delete a project
   */
  async delete(id: number): Promise<void> {
    return apiService.delete(API_ENDPOINTS.PROJECTS.BY_ID(id));
  }
}

export class TextService {
  /**
   * Create a new text document
   */
  async create(textData: TextCreate): Promise<Text> {
    return apiService.post<Text>(API_ENDPOINTS.TEXTS.BASE, textData);
  }

  /**
   * Upload a text file
   */
  async upload(
    projectId: number,
    file: File,
    options?: {
      title?: string;
      language?: string;
      onProgress?: (progress: number) => void;
    }
  ): Promise<Text> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId.toString());
    
    if (options?.title) {
      formData.append('title', options.title);
    }
    if (options?.language) {
      formData.append('language', options.language);
    }

    return apiService.upload<Text>(
      API_ENDPOINTS.TEXTS.UPLOAD,
      formData,
      options?.onProgress
    );
  }

  /**
   * Get list of texts with optional filters
   */
  async list(params?: QueryParams & {
    project_id?: number;
  }): Promise<Text[]> {
    return apiService.get<Text[]>(API_ENDPOINTS.TEXTS.BASE, params);
  }

  /**
   * Get a specific text by ID
   */
  async getById(id: number): Promise<Text> {
    return apiService.get<Text>(API_ENDPOINTS.TEXTS.BY_ID(id));
  }

  /**
   * Update a text
   */
  async update(id: number, textData: TextUpdate): Promise<Text> {
    return apiService.put<Text>(API_ENDPOINTS.TEXTS.BY_ID(id), textData);
  }

  /**
   * Delete a text
   */
  async delete(id: number): Promise<void> {
    return apiService.delete(API_ENDPOINTS.TEXTS.BY_ID(id));
  }
}

export const projectService = new ProjectService();
export const textService = new TextService();
export default projectService;
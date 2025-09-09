import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { Project, ProjectSettings, LabelSchema } from '@/types/api';
import Loading from '@/components/common/Loading';

interface CreateProjectPageProps {}

interface ProjectFormData {
  name: string;
  description: string;
  settings: {
    allow_overlapping_annotations: boolean;
    require_label_validation: boolean;
    auto_save_interval: number;
    annotation_guidelines: string;
  };
}

const initialFormData: ProjectFormData = {
  name: '',
  description: '',
  settings: {
    allow_overlapping_annotations: false,
    require_label_validation: true,
    auto_save_interval: 30,
    annotation_guidelines: ''
  }
};

export function CreateProjectPage({}: CreateProjectPageProps) {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<ProjectFormData>(initialFormData);
  const [errors, setErrors] = useState<Partial<Record<keyof ProjectFormData, string>>>({});
  const [loading, setLoading] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof ProjectFormData, string>> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Project name is required';
    } else if (formData.name.trim().length < 3) {
      newErrors.name = 'Project name must be at least 3 characters';
    } else if (formData.name.trim().length > 100) {
      newErrors.name = 'Project name must not exceed 100 characters';
    }

    if (formData.description && formData.description.length > 500) {
      newErrors.description = 'Description must not exceed 500 characters';
    }

    if (formData.settings.auto_save_interval < 10 || formData.settings.auto_save_interval > 300) {
      newErrors.settings = 'Auto-save interval must be between 10 and 300 seconds';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      // Create default label schema
      const defaultLabelSchema: LabelSchema = {
        id: Date.now().toString(),
        name: 'Default Labels',
        labels: [
          {
            id: '1',
            name: 'Entity',
            color: '#3b82f6',
            description: 'Named entities',
            shortcut_key: 'e'
          },
          {
            id: '2',
            name: 'Relationship',
            color: '#10b981',
            description: 'Relationships between entities',
            shortcut_key: 'r'
          },
          {
            id: '3',
            name: 'Event',
            color: '#f59e0b',
            description: 'Events and actions',
            shortcut_key: 'v'
          }
        ]
      };

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500));

      const newProject: Project = {
        id: Date.now().toString(),
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        created_by: 'current-user', // This would come from auth context
        status: 'active',
        texts_count: 0,
        annotations_count: 0,
        members_count: 1,
        settings: {
          ...formData.settings,
          label_schema: defaultLabelSchema
        }
      };

      toast.success('Project created successfully!');
      navigate(`/projects/${newProject.id}`);
      
    } catch (error) {
      console.error('Error creating project:', error);
      toast.error('Failed to create project. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (
    field: keyof ProjectFormData,
    value: string | boolean | number
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));

    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: undefined
      }));
    }
  };

  const handleSettingsChange = (
    field: keyof ProjectFormData['settings'],
    value: string | boolean | number
  ) => {
    setFormData(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        [field]: value
      }
    }));

    // Clear error when user changes settings
    if (errors.settings) {
      setErrors(prev => ({
        ...prev,
        settings: undefined
      }));
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/projects')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Projects
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Create New Project</h1>
        <p className="mt-2 text-gray-600">
          Set up a new annotation project with custom settings and guidelines
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Basic Information */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Basic Information</h2>
          </div>
          
          <div className="px-6 py-6 space-y-6">
            {/* Project Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Project Name *
              </label>
              <input
                type="text"
                id="name"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                className={`form-input ${errors.name ? 'border-red-300 focus:ring-red-500 focus:border-red-500' : ''}`}
                placeholder="Enter project name..."
                maxLength={100}
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-600">{errors.name}</p>
              )}
              <p className="mt-1 text-sm text-gray-500">
                {formData.name.length}/100 characters
              </p>
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                id="description"
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                rows={4}
                className={`form-textarea ${errors.description ? 'border-red-300 focus:ring-red-500 focus:border-red-500' : ''}`}
                placeholder="Describe the purpose and scope of your project..."
                maxLength={500}
              />
              {errors.description && (
                <p className="mt-1 text-sm text-red-600">{errors.description}</p>
              )}
              <p className="mt-1 text-sm text-gray-500">
                {formData.description.length}/500 characters
              </p>
            </div>
          </div>
        </div>

        {/* Annotation Settings */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Annotation Settings</h2>
            <p className="mt-1 text-sm text-gray-500">
              Configure how annotations work in this project
            </p>
          </div>
          
          <div className="px-6 py-6 space-y-6">
            {/* Allow Overlapping Annotations */}
            <div className="flex items-start">
              <div className="flex items-center h-5">
                <input
                  id="allow_overlapping"
                  type="checkbox"
                  checked={formData.settings.allow_overlapping_annotations}
                  onChange={(e) => handleSettingsChange('allow_overlapping_annotations', e.target.checked)}
                  className="form-checkbox"
                />
              </div>
              <div className="ml-3">
                <label htmlFor="allow_overlapping" className="font-medium text-gray-700">
                  Allow Overlapping Annotations
                </label>
                <p className="text-sm text-gray-500">
                  Multiple annotations can cover the same text span
                </p>
              </div>
            </div>

            {/* Require Label Validation */}
            <div className="flex items-start">
              <div className="flex items-center h-5">
                <input
                  id="require_validation"
                  type="checkbox"
                  checked={formData.settings.require_label_validation}
                  onChange={(e) => handleSettingsChange('require_label_validation', e.target.checked)}
                  className="form-checkbox"
                />
              </div>
              <div className="ml-3">
                <label htmlFor="require_validation" className="font-medium text-gray-700">
                  Require Label Validation
                </label>
                <p className="text-sm text-gray-500">
                  Annotations must be validated before being considered complete
                </p>
              </div>
            </div>

            {/* Auto-save Interval */}
            <div>
              <label htmlFor="auto_save" className="block text-sm font-medium text-gray-700 mb-2">
                Auto-save Interval (seconds)
              </label>
              <div className="flex items-center space-x-4">
                <input
                  type="number"
                  id="auto_save"
                  value={formData.settings.auto_save_interval}
                  onChange={(e) => handleSettingsChange('auto_save_interval', parseInt(e.target.value))}
                  min={10}
                  max={300}
                  className="form-input w-24"
                />
                <div className="flex items-center text-sm text-gray-500">
                  <InformationCircleIcon className="h-4 w-4 mr-1" />
                  Between 10 and 300 seconds
                </div>
              </div>
              {errors.settings && (
                <p className="mt-1 text-sm text-red-600">{errors.settings}</p>
              )}
            </div>
          </div>
        </div>

        {/* Annotation Guidelines */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Annotation Guidelines</h2>
            <p className="mt-1 text-sm text-gray-500">
              Provide instructions for annotators (optional)
            </p>
          </div>
          
          <div className="px-6 py-6">
            <textarea
              value={formData.settings.annotation_guidelines}
              onChange={(e) => handleSettingsChange('annotation_guidelines', e.target.value)}
              rows={6}
              className="form-textarea"
              placeholder="Enter detailed guidelines for annotators..."
            />
            <p className="mt-2 text-sm text-gray-500">
              These guidelines will be shown to annotators when they work on texts in this project.
            </p>
          </div>
        </div>

        {/* Form Actions */}
        <div className="flex items-center justify-end space-x-4 pt-6 border-t border-gray-200">
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loading className="inline w-4 h-4 mr-2" />
                Creating Project...
              </>
            ) : (
              'Create Project'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreateProjectPage;
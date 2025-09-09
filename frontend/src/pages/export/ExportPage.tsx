import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  DocumentIcon,
  CalendarIcon,
  UserIcon,
  TagIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { ExportOptions, ExportJob, Project, User, Label } from '@/types/api';
import Loading from '@/components/common/Loading';

interface ExportPageProps {}

const EXPORT_FORMATS = [
  {
    value: 'json',
    label: 'JSON',
    description: 'Structured format with full metadata support',
    extension: '.json'
  },
  {
    value: 'csv',
    label: 'CSV',
    description: 'Comma-separated values for spreadsheet applications',
    extension: '.csv'
  },
  {
    value: 'xml',
    label: 'XML',
    description: 'Extensible markup language format',
    extension: '.xml'
  },
  {
    value: 'conll',
    label: 'CoNLL',
    description: 'Conference on Natural Language Learning format',
    extension: '.conll'
  }
];

export function ExportPage({}: ExportPageProps) {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [availableUsers, setAvailableUsers] = useState<User[]>([]);
  const [availableLabels, setAvailableLabels] = useState<Label[]>([]);
  const [recentExports, setRecentExports] = useState<ExportJob[]>([]);
  
  const [exportOptions, setExportOptions] = useState<ExportOptions>({
    format: 'json',
    include_metadata: true,
    include_confidence: true,
    include_notes: true,
    filter_by_user: [],
    filter_by_label: [],
    date_range: undefined
  });

  useEffect(() => {
    const fetchData = async () => {
      if (!projectId) return;

      try {
        setLoading(true);
        // Simulate API calls
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Mock project data
        const mockProject: Project = {
          id: projectId,
          name: 'Medical Text Analysis',
          description: 'Analyzing medical literature for disease mentions and treatments',
          created_at: '2023-12-01T10:00:00Z',
          updated_at: '2023-12-15T14:30:00Z',
          created_by: 'user1',
          status: 'active',
          texts_count: 45,
          annotations_count: 1234,
          members_count: 8,
          settings: {
            allow_overlapping_annotations: true,
            require_label_validation: false,
            auto_save_interval: 30,
            label_schema: {
              id: '1',
              name: 'Medical Labels',
              labels: [
                {
                  id: '1',
                  name: 'Disease',
                  color: '#ef4444',
                  description: 'Disease mentions'
                },
                {
                  id: '2',
                  name: 'Treatment',
                  color: '#10b981',
                  description: 'Treatment procedures'
                },
                {
                  id: '3',
                  name: 'Symptom',
                  color: '#f59e0b',
                  description: 'Symptom descriptions'
                }
              ]
            }
          }
        };

        // Mock users data
        const mockUsers: User[] = [
          {
            id: 'user1',
            username: 'researcher1',
            email: 'researcher1@example.com',
            full_name: 'Dr. Sarah Johnson',
            role: 'manager',
            created_at: '2023-11-01T00:00:00Z',
            is_active: true
          },
          {
            id: 'user2',
            username: 'annotator1',
            email: 'annotator1@example.com',
            full_name: 'Mike Chen',
            role: 'annotator',
            created_at: '2023-11-15T00:00:00Z',
            is_active: true
          },
          {
            id: 'user3',
            username: 'annotator2',
            email: 'annotator2@example.com',
            full_name: 'Lisa Wang',
            role: 'annotator',
            created_at: '2023-11-20T00:00:00Z',
            is_active: true
          }
        ];

        // Mock recent exports
        const mockRecentExports: ExportJob[] = [
          {
            id: '1',
            project_id: projectId,
            created_by: 'user1',
            options: {
              format: 'json',
              include_metadata: true,
              include_confidence: true,
              include_notes: false
            },
            status: 'completed',
            progress: 100,
            created_at: '2023-12-14T10:30:00Z',
            completed_at: '2023-12-14T10:32:00Z',
            download_url: '/exports/medical-annotations-20231214.json'
          },
          {
            id: '2',
            project_id: projectId,
            created_by: 'user2',
            options: {
              format: 'csv',
              include_metadata: false,
              include_confidence: false,
              include_notes: true
            },
            status: 'completed',
            progress: 100,
            created_at: '2023-12-13T14:15:00Z',
            completed_at: '2023-12-13T14:16:00Z',
            download_url: '/exports/medical-annotations-20231213.csv'
          }
        ];

        setProject(mockProject);
        setAvailableUsers(mockUsers);
        setAvailableLabels(mockProject.settings.label_schema.labels);
        setRecentExports(mockRecentExports);
      } catch (error) {
        console.error('Error fetching export data:', error);
        toast.error('Failed to load export options');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId]);

  const handleExport = async () => {
    if (!project) return;

    try {
      setExporting(true);

      // Create export job
      const exportJob: ExportJob = {
        id: Date.now().toString(),
        project_id: project.id,
        created_by: 'current-user',
        options: exportOptions,
        status: 'pending',
        progress: 0,
        created_at: new Date().toISOString()
      };

      // Simulate export process
      toast.success('Export job started');
      
      // Navigate to progress page
      navigate(`/projects/${projectId}/export/${exportJob.id}/progress`);
      
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to start export');
    } finally {
      setExporting(false);
    }
  };

  const handleDownload = (exportJob: ExportJob) => {
    if (exportJob.download_url) {
      // In a real app, this would download the file
      window.open(exportJob.download_url, '_blank');
      toast.success('Download started');
    }
  };

  const getFormatDescription = (format: string) => {
    return EXPORT_FORMATS.find(f => f.value === format)?.description || '';
  };

  const getStatusIcon = (status: ExportJob['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <ExclamationCircleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <DocumentIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  if (loading) {
    return <Loading fullScreen text="Loading export options..." />;
  }

  if (!project) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-900">Project not found</h3>
          <p className="mt-1 text-sm text-gray-500">
            The project you're looking for doesn't exist or you don't have access to it.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Project
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Export Annotations</h1>
        <p className="mt-2 text-gray-600">
          Export annotations from "{project.name}" in various formats
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Export Configuration */}
        <div className="lg:col-span-2 space-y-6">
          {/* Format Selection */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Export Format</h2>
            </div>
            <div className="px-6 py-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {EXPORT_FORMATS.map((format) => (
                  <label key={format.value} className="relative">
                    <input
                      type="radio"
                      name="format"
                      value={format.value}
                      checked={exportOptions.format === format.value}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        format: e.target.value as ExportOptions['format']
                      })}
                      className="sr-only"
                    />
                    <div className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      exportOptions.format === format.value
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold text-gray-900">
                          {format.label}
                        </h3>
                        <span className="text-xs text-gray-500">
                          {format.extension}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600">
                        {format.description}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Export Options */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Export Options</h2>
            </div>
            <div className="px-6 py-6 space-y-6">
              {/* Include Options */}
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-4">Include Data</h3>
                <div className="space-y-3">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={exportOptions.include_metadata}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        include_metadata: e.target.checked
                      })}
                      className="form-checkbox"
                    />
                    <span className="ml-3 text-sm text-gray-700">
                      Include metadata (file names, upload dates, etc.)
                    </span>
                  </label>

                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={exportOptions.include_confidence}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        include_confidence: e.target.checked
                      })}
                      className="form-checkbox"
                    />
                    <span className="ml-3 text-sm text-gray-700">
                      Include confidence scores
                    </span>
                  </label>

                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={exportOptions.include_notes}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        include_notes: e.target.checked
                      })}
                      className="form-checkbox"
                    />
                    <span className="ml-3 text-sm text-gray-700">
                      Include annotation notes
                    </span>
                  </label>
                </div>
              </div>

              {/* User Filter */}
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-4">Filter by Annotator</h3>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {availableUsers.map((user) => (
                    <label key={user.id} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={exportOptions.filter_by_user?.includes(user.id) || false}
                        onChange={(e) => {
                          const currentFilters = exportOptions.filter_by_user || [];
                          if (e.target.checked) {
                            setExportOptions({
                              ...exportOptions,
                              filter_by_user: [...currentFilters, user.id]
                            });
                          } else {
                            setExportOptions({
                              ...exportOptions,
                              filter_by_user: currentFilters.filter(id => id !== user.id)
                            });
                          }
                        }}
                        className="form-checkbox"
                      />
                      <span className="ml-3 text-sm text-gray-700">
                        {user.full_name || user.username}
                      </span>
                    </label>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Leave unselected to include annotations from all users
                </p>
              </div>

              {/* Label Filter */}
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-4">Filter by Label</h3>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {availableLabels.map((label) => (
                    <label key={label.id} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={exportOptions.filter_by_label?.includes(label.id) || false}
                        onChange={(e) => {
                          const currentFilters = exportOptions.filter_by_label || [];
                          if (e.target.checked) {
                            setExportOptions({
                              ...exportOptions,
                              filter_by_label: [...currentFilters, label.id]
                            });
                          } else {
                            setExportOptions({
                              ...exportOptions,
                              filter_by_label: currentFilters.filter(id => id !== label.id)
                            });
                          }
                        }}
                        className="form-checkbox"
                      />
                      <span className="ml-3 text-sm text-gray-700 flex items-center">
                        <span 
                          className="w-3 h-3 rounded-full mr-2"
                          style={{ backgroundColor: label.color }}
                        ></span>
                        {label.name}
                      </span>
                    </label>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Leave unselected to include all labels
                </p>
              </div>

              {/* Date Range */}
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-4">Date Range</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      From
                    </label>
                    <input
                      type="date"
                      value={exportOptions.date_range?.start || ''}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        date_range: {
                          start: e.target.value,
                          end: exportOptions.date_range?.end || ''
                        }
                      })}
                      className="form-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      To
                    </label>
                    <input
                      type="date"
                      value={exportOptions.date_range?.end || ''}
                      onChange={(e) => setExportOptions({
                        ...exportOptions,
                        date_range: {
                          start: exportOptions.date_range?.start || '',
                          end: e.target.value
                        }
                      })}
                      className="form-input"
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Leave empty to include all dates
                </p>
              </div>
            </div>
          </div>

          {/* Export Button */}
          <div className="flex justify-end">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="btn btn-primary btn-lg"
            >
              {exporting ? (
                <>
                  <div className="inline-flex items-center">
                    <div className="animate-spin -ml-1 mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                    Starting Export...
                  </div>
                </>
              ) : (
                <>
                  <ArrowDownTrayIcon className="h-5 w-5 mr-2" />
                  Start Export
                </>
              )}
            </button>
          </div>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6">
          {/* Export Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5 mr-3 flex-shrink-0" />
              <div className="text-sm text-blue-700">
                <p className="font-medium mb-2">Export Information</p>
                <ul className="space-y-1">
                  <li>• {project.annotations_count} total annotations</li>
                  <li>• {project.texts_count} text documents</li>
                  <li>• {availableLabels.length} label types</li>
                  <li>• {availableUsers.length} contributors</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Recent Exports */}
          {recentExports.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900">Recent Exports</h3>
              </div>
              <div className="px-4 py-4">
                <div className="space-y-3">
                  {recentExports.map((exportJob) => (
                    <div key={exportJob.id} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        {getStatusIcon(exportJob.status)}
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {exportJob.options.format.toUpperCase()}
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(exportJob.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      {exportJob.status === 'completed' && exportJob.download_url && (
                        <button
                          onClick={() => handleDownload(exportJob)}
                          className="text-primary-600 hover:text-primary-900 text-sm font-medium"
                        >
                          Download
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ExportPage;
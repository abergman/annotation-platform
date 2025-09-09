import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  PlusIcon, 
  MagnifyingGlassIcon, 
  FunnelIcon,
  DocumentTextIcon,
  ArrowUpTrayIcon,
  EyeIcon,
  PencilIcon,
  TrashIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowLeftIcon,
  EllipsisVerticalIcon
} from '@heroicons/react/24/outline';
import { Menu } from '@headlessui/react';
import toast from 'react-hot-toast';
import { Text, TextFilter, SearchOptions, SortOptions, Project } from '@/types/api';
import Loading from '@/components/common/Loading';

interface TextsPageProps {}

interface TextCardProps {
  text: Text;
  onView: (text: Text) => void;
  onEdit: (text: Text) => void;
  onDelete: (text: Text) => void;
  onAnnotate: (text: Text) => void;
}

function TextCard({ text, onView, onEdit, onDelete, onAnnotate }: TextCardProps) {
  const statusConfig = {
    processing: { 
      color: 'text-yellow-600 bg-yellow-100', 
      icon: ClockIcon,
      label: 'Processing' 
    },
    ready: { 
      color: 'text-green-600 bg-green-100', 
      icon: CheckCircleIcon,
      label: 'Ready' 
    },
    annotating: { 
      color: 'text-blue-600 bg-blue-100', 
      icon: PencilIcon,
      label: 'In Progress' 
    },
    completed: { 
      color: 'text-gray-600 bg-gray-100', 
      icon: CheckCircleIcon,
      label: 'Completed' 
    }
  };

  const status = statusConfig[text.status];
  const StatusIcon = status.icon;

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 truncate mb-2">
              {text.title}
            </h3>
            <p className="text-sm text-gray-600 mb-2">
              {text.file_name} • {formatFileSize(text.file_size)}
            </p>
          </div>
          
          <Menu as="div" className="relative ml-4 flex-shrink-0">
            <Menu.Button className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
              <EllipsisVerticalIcon className="h-5 w-5 text-gray-500" />
            </Menu.Button>
            <Menu.Items className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-10">
              <div className="py-1">
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={() => onView(text)}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                    >
                      <EyeIcon className="h-4 w-4 mr-2" />
                      View Text
                    </button>
                  )}
                </Menu.Item>
                {text.status === 'ready' && (
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={() => onAnnotate(text)}
                        className={`${
                          active ? 'bg-gray-100' : ''
                        } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                      >
                        <PencilIcon className="h-4 w-4 mr-2" />
                        Annotate
                      </button>
                    )}
                  </Menu.Item>
                )}
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={() => onEdit(text)}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                    >
                      <PencilIcon className="h-4 w-4 mr-2" />
                      Edit Metadata
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={() => onDelete(text)}
                      className={`${
                        active ? 'bg-red-50' : ''
                      } flex items-center px-4 py-2 text-sm text-red-600 w-full text-left`}
                    >
                      <TrashIcon className="h-4 w-4 mr-2" />
                      Delete Text
                    </button>
                  )}
                </Menu.Item>
              </div>
            </Menu.Items>
          </Menu>
        </div>

        <div className="flex items-center justify-between mb-4">
          <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.color}`}>
            <StatusIcon className="h-3 w-3 mr-1" />
            {status.label}
          </div>
          <div className="text-xs text-gray-500">
            {text.annotations_count} annotations
          </div>
        </div>

        <div className="text-sm text-gray-600 mb-4 line-clamp-3">
          {text.content.substring(0, 150)}...
        </div>

        <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
          <span>Uploaded {new Date(text.uploaded_at).toLocaleDateString()}</span>
        </div>

        <div className="flex space-x-2">
          <button
            onClick={() => onView(text)}
            className="btn btn-secondary btn-sm flex-1"
          >
            <EyeIcon className="h-4 w-4 mr-1" />
            View
          </button>
          {text.status === 'ready' && (
            <button
              onClick={() => onAnnotate(text)}
              className="btn btn-primary btn-sm flex-1"
            >
              <PencilIcon className="h-4 w-4 mr-1" />
              Annotate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function FilterPanel({ 
  filters, 
  onFiltersChange,
  onClear
}: {
  filters: TextFilter;
  onFiltersChange: (filters: TextFilter) => void;
  onClear: () => void;
}) {
  return (
    <div className="bg-white p-4 border-b">
      <div className="flex flex-wrap gap-4 items-center">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Status
          </label>
          <select 
            multiple
            value={filters.status || []}
            onChange={(e) => {
              const values = Array.from(e.target.selectedOptions, option => option.value);
              onFiltersChange({ ...filters, status: values });
            }}
            className="form-select text-sm"
          >
            <option value="processing">Processing</option>
            <option value="ready">Ready</option>
            <option value="annotating">In Progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Upload Date Range
          </label>
          <div className="flex gap-2">
            <input
              type="date"
              value={filters.date_range?.start || ''}
              onChange={(e) => onFiltersChange({
                ...filters,
                date_range: {
                  start: e.target.value,
                  end: filters.date_range?.end || ''
                }
              })}
              className="form-input text-sm"
            />
            <input
              type="date"
              value={filters.date_range?.end || ''}
              onChange={(e) => onFiltersChange({
                ...filters,
                date_range: {
                  start: filters.date_range?.start || '',
                  end: e.target.value
                }
              })}
              className="form-input text-sm"
            />
          </div>
        </div>

        <button
          onClick={onClear}
          className="btn btn-secondary btn-sm"
        >
          Clear Filters
        </button>
      </div>
    </div>
  );
}

export function TextsPage({}: TextsPageProps) {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [texts, setTexts] = useState<Text[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchOptions, setSearchOptions] = useState<SearchOptions>({ query: '' });
  const [filters, setFilters] = useState<TextFilter>({});
  const [sortOptions, setSortOptions] = useState<SortOptions>({ field: 'uploaded_at', direction: 'desc' });
  const [showFilters, setShowFilters] = useState(false);

  // Mock data - replace with actual API calls
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
          texts_count: 3,
          annotations_count: 45,
          members_count: 8,
          settings: {
            allow_overlapping_annotations: true,
            require_label_validation: false,
            auto_save_interval: 30,
            label_schema: {
              id: '1',
              name: 'Medical Labels',
              labels: []
            }
          }
        };

        // Mock texts data
        const mockTexts: Text[] = [
          {
            id: '1',
            title: 'Clinical Trial Report #1',
            content: 'This is a comprehensive clinical trial report examining the efficacy of a new treatment protocol...',
            project_id: projectId,
            uploaded_at: '2023-12-10T10:00:00Z',
            uploaded_by: 'user1',
            status: 'ready',
            annotations_count: 15,
            file_name: 'clinical_trial_001.txt',
            file_size: 45678,
            metadata: { source: 'clinical_database' }
          },
          {
            id: '2',
            title: 'Research Paper Abstract Collection',
            content: 'A collection of abstracts from recent research papers in the medical field...',
            project_id: projectId,
            uploaded_at: '2023-12-12T14:30:00Z',
            uploaded_by: 'user2',
            status: 'annotating',
            annotations_count: 23,
            file_name: 'abstracts_collection.txt',
            file_size: 78923,
            metadata: { source: 'pubmed' }
          },
          {
            id: '3',
            title: 'Patient Case Studies',
            content: 'Anonymized patient case studies for training and research purposes...',
            project_id: projectId,
            uploaded_at: '2023-12-14T09:15:00Z',
            uploaded_by: 'user1',
            status: 'processing',
            annotations_count: 0,
            file_name: 'case_studies.txt',
            file_size: 123456,
            metadata: { source: 'hospital_records' }
          }
        ];

        setProject(mockProject);
        setTexts(mockTexts);
        setError(null);
      } catch (err) {
        setError('Failed to load texts');
        console.error('Error fetching texts:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId, filters, searchOptions, sortOptions]);

  const filteredTexts = useMemo(() => {
    let result = [...texts];

    // Apply search
    if (searchOptions.query) {
      result = result.filter(text =>
        text.title.toLowerCase().includes(searchOptions.query.toLowerCase()) ||
        text.file_name.toLowerCase().includes(searchOptions.query.toLowerCase()) ||
        text.content.toLowerCase().includes(searchOptions.query.toLowerCase())
      );
    }

    // Apply filters
    if (filters.status && filters.status.length > 0) {
      result = result.filter(text => filters.status!.includes(text.status));
    }

    // Apply sorting
    result.sort((a, b) => {
      const aValue = a[sortOptions.field as keyof Text];
      const bValue = b[sortOptions.field as keyof Text];
      
      if (sortOptions.direction === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return result;
  }, [texts, searchOptions, filters, sortOptions]);

  const handleView = (text: Text) => {
    navigate(`/projects/${projectId}/texts/${text.id}/view`);
  };

  const handleEdit = (text: Text) => {
    navigate(`/projects/${projectId}/texts/${text.id}/edit`);
  };

  const handleDelete = async (text: Text) => {
    if (!window.confirm(`Are you sure you want to delete "${text.title}"? This action cannot be undone.`)) {
      return;
    }

    try {
      // Simulate API call
      toast.success(`Text "${text.title}" deleted successfully`);
      setTexts(prev => prev.filter(t => t.id !== text.id));
    } catch (err) {
      toast.error('Failed to delete text');
    }
  };

  const handleAnnotate = (text: Text) => {
    navigate(`/projects/${projectId}/texts/${text.id}/annotate`);
  };

  const clearFilters = () => {
    setFilters({});
    setSearchOptions({ query: '' });
  };

  if (loading) {
    return <Loading fullScreen text="Loading texts..." />;
  }

  if (!project) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900">Project not found</h3>
          <p className="mt-1 text-sm text-gray-500">
            The project you're looking for doesn't exist or you don't have access to it.
          </p>
          <div className="mt-6">
            <Link to="/projects" className="btn btn-primary">
              Back to Projects
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Project
        </button>
        
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{project.name} - Texts</h1>
            <p className="mt-2 text-gray-600">
              Manage and annotate texts in this project
            </p>
          </div>
          <div className="mt-4 sm:mt-0 flex space-x-3">
            <Link
              to={`/projects/${projectId}/texts/upload`}
              className="btn btn-secondary"
            >
              <ArrowUpTrayIcon className="h-5 w-5 mr-2" />
              Upload Texts
            </Link>
          </div>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
        <div className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search texts..."
                value={searchOptions.query}
                onChange={(e) => setSearchOptions({ ...searchOptions, query: e.target.value })}
                className="form-input pl-10"
              />
            </div>

            {/* Sort */}
            <div className="flex gap-2">
              <select
                value={sortOptions.field}
                onChange={(e) => setSortOptions({ ...sortOptions, field: e.target.value })}
                className="form-select"
              >
                <option value="uploaded_at">Upload Date</option>
                <option value="title">Title</option>
                <option value="annotations_count">Annotations</option>
                <option value="status">Status</option>
              </select>
              <select
                value={sortOptions.direction}
                onChange={(e) => setSortOptions({ ...sortOptions, direction: e.target.value as 'asc' | 'desc' })}
                className="form-select"
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>

            {/* Filter Toggle */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`btn ${showFilters ? 'btn-primary' : 'btn-secondary'}`}
            >
              <FunnelIcon className="h-5 w-5 mr-2" />
              Filters
            </button>
          </div>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            onClear={clearFilters}
          />
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <div className="flex">
            <div className="text-sm text-red-600">{error}</div>
          </div>
        </div>
      )}

      {/* Texts Grid */}
      {filteredTexts.length === 0 ? (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 text-gray-400 mb-4">
            <DocumentTextIcon className="h-full w-full" />
          </div>
          <h3 className="mt-2 text-sm font-semibold text-gray-900">No texts found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchOptions.query || Object.keys(filters).length > 0
              ? 'Try adjusting your search or filters'
              : 'Get started by uploading your first text'
            }
          </p>
          {(!searchOptions.query && Object.keys(filters).length === 0) && (
            <div className="mt-6">
              <Link
                to={`/projects/${projectId}/texts/upload`}
                className="btn btn-primary"
              >
                <ArrowUpTrayIcon className="h-5 w-5 mr-2" />
                Upload Texts
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTexts.map((text) => (
            <TextCard
              key={text.id}
              text={text}
              onView={handleView}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onAnnotate={handleAnnotate}
            />
          ))}
        </div>
      )}

      {/* Results Summary */}
      {filteredTexts.length > 0 && (
        <div className="mt-6 text-sm text-gray-500 text-center">
          Showing {filteredTexts.length} of {texts.length} texts
        </div>
      )}
    </div>
  );
}

export default TextsPage;
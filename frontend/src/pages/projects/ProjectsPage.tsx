import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  PlusIcon, 
  MagnifyingGlassIcon, 
  FunnelIcon,
  DocumentTextIcon,
  UsersIcon,
  ClockIcon,
  CheckCircleIcon,
  ArchiveBoxIcon,
  EllipsisVerticalIcon
} from '@heroicons/react/24/outline';
import { Menu } from '@headlessui/react';
import toast from 'react-hot-toast';
import { Project, ProjectFilter, SearchOptions, SortOptions, PaginationOptions } from '@/types/api';
import Loading from '@/components/common/Loading';

interface ProjectsPageProps {}

interface ProjectCardProps {
  project: Project;
  onEdit: (project: Project) => void;
  onDelete: (project: Project) => void;
  onArchive: (project: Project) => void;
}

function ProjectCard({ project, onEdit, onDelete, onArchive }: ProjectCardProps) {
  const navigate = useNavigate();

  const statusConfig = {
    active: { 
      color: 'text-green-600 bg-green-100', 
      icon: CheckCircleIcon,
      label: 'Active' 
    },
    completed: { 
      color: 'text-blue-600 bg-blue-100', 
      icon: CheckCircleIcon,
      label: 'Completed' 
    },
    archived: { 
      color: 'text-gray-600 bg-gray-100', 
      icon: ArchiveBoxIcon,
      label: 'Archived' 
    }
  };

  const status = statusConfig[project.status];
  const StatusIcon = status.icon;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 truncate mb-2">
              {project.name}
            </h3>
            {project.description && (
              <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                {project.description}
              </p>
            )}
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
                      onClick={() => onEdit(project)}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                    >
                      Edit Project
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={() => onArchive(project)}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                    >
                      {project.status === 'archived' ? 'Unarchive' : 'Archive'}
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={() => onDelete(project)}
                      className={`${
                        active ? 'bg-red-50' : ''
                      } flex items-center px-4 py-2 text-sm text-red-600 w-full text-left`}
                    >
                      Delete Project
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
            Created {new Date(project.created_at).toLocaleDateString()}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <DocumentTextIcon className="h-5 w-5 text-gray-400 mx-auto mb-1" />
            <div className="text-lg font-semibold text-gray-900">{project.texts_count}</div>
            <div className="text-xs text-gray-500">Texts</div>
          </div>
          <div className="text-center">
            <ClockIcon className="h-5 w-5 text-gray-400 mx-auto mb-1" />
            <div className="text-lg font-semibold text-gray-900">{project.annotations_count}</div>
            <div className="text-xs text-gray-500">Annotations</div>
          </div>
          <div className="text-center">
            <UsersIcon className="h-5 w-5 text-gray-400 mx-auto mb-1" />
            <div className="text-lg font-semibold text-gray-900">{project.members_count}</div>
            <div className="text-xs text-gray-500">Members</div>
          </div>
        </div>

        <button
          onClick={() => navigate(`/projects/${project.id}`)}
          className="w-full btn btn-primary btn-sm"
        >
          View Project
        </button>
      </div>
    </div>
  );
}

function FilterPanel({ 
  filters, 
  onFiltersChange,
  onClear
}: {
  filters: ProjectFilter;
  onFiltersChange: (filters: ProjectFilter) => void;
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
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Date Range
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

        <div className="flex items-center">
          <input
            type="checkbox"
            id="has-texts"
            checked={filters.has_texts || false}
            onChange={(e) => onFiltersChange({
              ...filters,
              has_texts: e.target.checked
            })}
            className="form-checkbox"
          />
          <label htmlFor="has-texts" className="ml-2 text-sm text-gray-700">
            Has texts
          </label>
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

export function ProjectsPage({}: ProjectsPageProps) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchOptions, setSearchOptions] = useState<SearchOptions>({ query: '' });
  const [filters, setFilters] = useState<ProjectFilter>({});
  const [sortOptions, setSortOptions] = useState<SortOptions>({ field: 'created_at', direction: 'desc' });
  const [pagination, setPagination] = useState<PaginationOptions>({ page: 1, per_page: 12 });
  const [showFilters, setShowFilters] = useState(false);
  const [totalProjects, setTotalProjects] = useState(0);

  // Mock data - replace with actual API calls
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const mockProjects: Project[] = [
          {
            id: '1',
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
                labels: []
              }
            }
          },
          {
            id: '2',
            name: 'Legal Document Review',
            description: 'Reviewing legal contracts for clause identification',
            created_at: '2023-11-15T09:00:00Z',
            updated_at: '2023-12-10T16:45:00Z',
            created_by: 'user2',
            status: 'completed',
            texts_count: 23,
            annotations_count: 567,
            members_count: 4,
            settings: {
              allow_overlapping_annotations: false,
              require_label_validation: true,
              auto_save_interval: 60,
              label_schema: {
                id: '2',
                name: 'Legal Labels',
                labels: []
              }
            }
          },
          {
            id: '3',
            name: 'Sentiment Analysis Study',
            description: 'Analyzing social media posts for sentiment classification',
            created_at: '2023-10-01T08:00:00Z',
            updated_at: '2023-10-30T12:00:00Z',
            created_by: 'user1',
            status: 'archived',
            texts_count: 156,
            annotations_count: 3421,
            members_count: 12,
            settings: {
              allow_overlapping_annotations: true,
              require_label_validation: true,
              auto_save_interval: 15,
              label_schema: {
                id: '3',
                name: 'Sentiment Labels',
                labels: []
              }
            }
          }
        ];

        setProjects(mockProjects);
        setTotalProjects(mockProjects.length);
        setError(null);
      } catch (err) {
        setError('Failed to load projects');
        console.error('Error fetching projects:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, [filters, searchOptions, sortOptions, pagination]);

  const filteredProjects = useMemo(() => {
    let result = [...projects];

    // Apply search
    if (searchOptions.query) {
      result = result.filter(project =>
        project.name.toLowerCase().includes(searchOptions.query.toLowerCase()) ||
        (project.description && project.description.toLowerCase().includes(searchOptions.query.toLowerCase()))
      );
    }

    // Apply filters
    if (filters.status && filters.status.length > 0) {
      result = result.filter(project => filters.status!.includes(project.status));
    }

    if (filters.has_texts) {
      result = result.filter(project => project.texts_count > 0);
    }

    // Apply sorting
    result.sort((a, b) => {
      const aValue = a[sortOptions.field as keyof Project];
      const bValue = b[sortOptions.field as keyof Project];
      
      if (sortOptions.direction === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return result;
  }, [projects, searchOptions, filters, sortOptions]);

  const handleEdit = (project: Project) => {
    navigate(`/projects/${project.id}/settings`);
  };

  const handleDelete = async (project: Project) => {
    if (!window.confirm(`Are you sure you want to delete "${project.name}"? This action cannot be undone.`)) {
      return;
    }

    try {
      // Simulate API call
      toast.success(`Project "${project.name}" deleted successfully`);
      setProjects(prev => prev.filter(p => p.id !== project.id));
    } catch (err) {
      toast.error('Failed to delete project');
    }
  };

  const handleArchive = async (project: Project) => {
    try {
      const newStatus = project.status === 'archived' ? 'active' : 'archived';
      
      // Simulate API call
      toast.success(
        `Project "${project.name}" ${newStatus === 'archived' ? 'archived' : 'unarchived'} successfully`
      );
      
      setProjects(prev =>
        prev.map(p =>
          p.id === project.id
            ? { ...p, status: newStatus as Project['status'] }
            : p
        )
      );
    } catch (err) {
      toast.error('Failed to update project status');
    }
  };

  const clearFilters = () => {
    setFilters({});
    setSearchOptions({ query: '' });
  };

  if (loading) {
    return <Loading fullScreen text="Loading projects..." />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Projects</h1>
          <p className="mt-2 text-gray-600">
            Manage your annotation projects and track progress
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Link
            to="/projects/create"
            className="btn btn-primary"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            Create Project
          </Link>
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
                placeholder="Search projects..."
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
                <option value="created_at">Created Date</option>
                <option value="updated_at">Updated Date</option>
                <option value="name">Name</option>
                <option value="texts_count">Text Count</option>
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

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 text-gray-400 mb-4">
            <DocumentTextIcon className="h-full w-full" />
          </div>
          <h3 className="mt-2 text-sm font-semibold text-gray-900">No projects found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchOptions.query || Object.keys(filters).length > 0
              ? 'Try adjusting your search or filters'
              : 'Get started by creating your first project'
            }
          </p>
          {(!searchOptions.query && Object.keys(filters).length === 0) && (
            <div className="mt-6">
              <Link
                to="/projects/create"
                className="btn btn-primary"
              >
                <PlusIcon className="h-5 w-5 mr-2" />
                Create Project
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onArchive={handleArchive}
            />
          ))}
        </div>
      )}

      {/* Results Summary */}
      {filteredProjects.length > 0 && (
        <div className="mt-6 text-sm text-gray-500 text-center">
          Showing {filteredProjects.length} of {totalProjects} projects
        </div>
      )}
    </div>
  );
}

export default ProjectsPage;
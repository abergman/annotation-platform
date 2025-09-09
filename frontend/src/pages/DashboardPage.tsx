import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { formatRelativeTime } from '@/utils/helpers';
import { 
  PlusIcon, 
  FolderOpenIcon, 
  DocumentTextIcon,
  TagIcon,
  UserGroupIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';

export function DashboardPage() {
  const { state } = useAuth();
  const { user } = state;

  // Mock data - will be replaced with real API data
  const stats = {
    projects: 3,
    texts: 15,
    annotations: 142,
    labels: 8
  };

  const recentProjects = [
    {
      id: 1,
      name: "Research Paper Analysis",
      description: "Analyzing sentiment in academic papers",
      updated_at: "2024-01-15T10:30:00Z",
      text_count: 8,
      annotation_count: 45
    },
    {
      id: 2,
      name: "News Article Classification",
      description: "Categorizing news articles by topic",
      updated_at: "2024-01-14T15:45:00Z",
      text_count: 12,
      annotation_count: 78
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Welcome Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Welcome back, {user?.full_name || user?.username}!
        </h1>
        <p className="text-gray-600">
          Here's what's happening with your annotation projects.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <button className="btn btn-primary btn-md p-6 h-auto flex flex-col items-center space-y-2">
          <PlusIcon className="h-8 w-8" />
          <span className="text-base font-medium">New Project</span>
          <span className="text-sm opacity-80">Create annotation project</span>
        </button>
        
        <button className="btn btn-outline btn-md p-6 h-auto flex flex-col items-center space-y-2">
          <DocumentTextIcon className="h-8 w-8" />
          <span className="text-base font-medium">Upload Text</span>
          <span className="text-sm opacity-80">Add documents to annotate</span>
        </button>
        
        <button className="btn btn-outline btn-md p-6 h-auto flex flex-col items-center space-y-2">
          <TagIcon className="h-8 w-8" />
          <span className="text-base font-medium">Manage Labels</span>
          <span className="text-sm opacity-80">Create annotation categories</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Statistics Cards */}
        <div className="lg:col-span-1">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Overview</h2>
          <div className="space-y-4">
            <div className="card">
              <div className="card-content flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{stats.projects}</p>
                  <p className="text-sm text-gray-600">Active Projects</p>
                </div>
                <FolderOpenIcon className="h-8 w-8 text-blue-500" />
              </div>
            </div>

            <div className="card">
              <div className="card-content flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{stats.texts}</p>
                  <p className="text-sm text-gray-600">Text Documents</p>
                </div>
                <DocumentTextIcon className="h-8 w-8 text-green-500" />
              </div>
            </div>

            <div className="card">
              <div className="card-content flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{stats.annotations}</p>
                  <p className="text-sm text-gray-600">Annotations Created</p>
                </div>
                <TagIcon className="h-8 w-8 text-purple-500" />
              </div>
            </div>

            <div className="card">
              <div className="card-content flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{stats.labels}</p>
                  <p className="text-sm text-gray-600">Label Categories</p>
                </div>
                <ChartBarIcon className="h-8 w-8 text-orange-500" />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Projects */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Recent Projects</h2>
            <button className="btn btn-outline btn-sm">
              View All Projects
            </button>
          </div>

          <div className="space-y-4">
            {recentProjects.map((project) => (
              <div key={project.id} className="card hover:shadow-md transition-shadow cursor-pointer">
                <div className="card-content">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="text-lg font-medium text-gray-900 mb-1">
                        {project.name}
                      </h3>
                      <p className="text-gray-600 text-sm mb-3">
                        {project.description}
                      </p>
                      
                      <div className="flex items-center space-x-4 text-sm text-gray-500">
                        <span className="flex items-center">
                          <DocumentTextIcon className="h-4 w-4 mr-1" />
                          {project.text_count} texts
                        </span>
                        <span className="flex items-center">
                          <TagIcon className="h-4 w-4 mr-1" />
                          {project.annotation_count} annotations
                        </span>
                        <span>
                          Updated {formatRelativeTime(project.updated_at)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <button className="btn btn-outline btn-sm">
                        View
                      </button>
                      <button className="btn btn-primary btn-sm">
                        Annotate
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {recentProjects.length === 0 && (
              <div className="card">
                <div className="card-content text-center py-12">
                  <FolderOpenIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No projects yet
                  </h3>
                  <p className="text-gray-600 mb-6">
                    Get started by creating your first annotation project.
                  </p>
                  <button className="btn btn-primary btn-md">
                    <PlusIcon className="h-5 w-5 mr-2" />
                    Create Project
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Activity Feed */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Activity</h2>
        <div className="card">
          <div className="card-content">
            <div className="space-y-3">
              <div className="flex items-center space-x-3 text-sm">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-600">
                  Added 5 new annotations to "Research Paper Analysis"
                </span>
                <span className="text-gray-400">2 hours ago</span>
              </div>
              <div className="flex items-center space-x-3 text-sm">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span className="text-gray-600">
                  Created new label "Methodology" in project
                </span>
                <span className="text-gray-400">Yesterday</span>
              </div>
              <div className="flex items-center space-x-3 text-sm">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span className="text-gray-600">
                  Uploaded 3 new documents for annotation
                </span>
                <span className="text-gray-400">2 days ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;
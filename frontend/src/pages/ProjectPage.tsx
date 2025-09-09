import React from 'react';
import { useParams } from 'react-router-dom';

export function ProjectPage() {
  const { projectId } = useParams();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Project Management
        </h1>
        <p className="text-gray-600 mb-6">
          Project ID: {projectId}
        </p>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <p className="text-blue-800">
            🚧 Project management interface is being developed. This will include:
          </p>
          <ul className="mt-4 text-blue-700 text-left max-w-md mx-auto">
            <li>• Project details and settings</li>
            <li>• Text document management</li>
            <li>• Label management interface</li>
            <li>• User access control</li>
            <li>• Progress tracking and statistics</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default ProjectPage;
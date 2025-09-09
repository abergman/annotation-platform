import React from 'react';
import { useAuth } from '@/contexts/AuthContext';

export function ProfilePage() {
  const { state } = useAuth();
  const { user } = state;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          User Profile
        </h1>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 max-w-2xl mx-auto">
          <p className="text-purple-800 mb-4">
            🚧 Profile management interface is being developed. This will include:
          </p>
          <ul className="text-purple-700 text-left mb-6">
            <li>• Profile information editing</li>
            <li>• Password change functionality</li>
            <li>• Notification preferences</li>
            <li>• Account settings</li>
            <li>• Activity history</li>
          </ul>
          <div className="bg-white rounded-lg p-4 text-left">
            <h3 className="font-medium text-gray-900 mb-2">Current User Info:</h3>
            <p><strong>Username:</strong> {user?.username}</p>
            <p><strong>Email:</strong> {user?.email}</p>
            <p><strong>Full Name:</strong> {user?.full_name || 'Not set'}</p>
            <p><strong>Institution:</strong> {user?.institution || 'Not set'}</p>
            <p><strong>Role:</strong> {user?.role}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProfilePage;
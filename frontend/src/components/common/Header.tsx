import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getInitials } from '@/utils/helpers';
import { 
  UserCircleIcon, 
  Cog6ToothIcon, 
  ArrowRightOnRectangleIcon,
  BookOpenIcon
} from '@heroicons/react/24/outline';
import { Menu } from '@headlessui/react';

export function Header() {
  const { state, logout } = useAuth();
  const { user, isAuthenticated } = state;

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Title */}
          <div className="flex items-center space-x-3">
            <BookOpenIcon className="h-8 w-8 text-primary-600" />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Text Annotation System
              </h1>
              <p className="text-xs text-gray-500 hidden sm:block">
                Academic research annotation platform
              </p>
            </div>
          </div>

          {/* User Menu */}
          {isAuthenticated && user ? (
            <Menu as="div" className="relative">
              <Menu.Button className="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {getInitials(user.full_name || user.username)}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-medium text-gray-900">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-xs text-gray-500">{user.role}</p>
                </div>
              </Menu.Button>

              <Menu.Items className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50">
                <div className="py-1">
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        className={`${
                          active ? 'bg-gray-100' : ''
                        } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                      >
                        <UserCircleIcon className="mr-3 h-4 w-4" />
                        Profile
                      </button>
                    )}
                  </Menu.Item>

                  <Menu.Item>
                    {({ active }) => (
                      <button
                        className={`${
                          active ? 'bg-gray-100' : ''
                        } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                      >
                        <Cog6ToothIcon className="mr-3 h-4 w-4" />
                        Settings
                      </button>
                    )}
                  </Menu.Item>

                  <div className="border-t border-gray-100" />
                  
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={handleLogout}
                        className={`${
                          active ? 'bg-gray-100' : ''
                        } flex items-center px-4 py-2 text-sm text-gray-700 w-full text-left`}
                      >
                        <ArrowRightOnRectangleIcon className="mr-3 h-4 w-4" />
                        Sign out
                      </button>
                    )}
                  </Menu.Item>
                </div>
              </Menu.Items>
            </Menu>
          ) : (
            <div className="flex items-center space-x-3">
              <span className="text-sm text-gray-600">Welcome to Text Annotation</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;
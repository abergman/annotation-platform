import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LoginForm from '@/components/auth/LoginForm';
import RegisterForm from '@/components/auth/RegisterForm';
import toast from 'react-hot-toast';

type AuthMode = 'login' | 'register';

export function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const navigate = useNavigate();

  const handleAuthSuccess = () => {
    toast.success(mode === 'login' ? 'Welcome back!' : 'Account created successfully!');
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 flex items-center justify-center rounded-full bg-primary-100">
            <svg
              className="h-8 w-8 text-primary-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Text Annotation System
          </h2>
          <p className="mt-2 text-sm text-gray-600 max-w-sm mx-auto">
            A comprehensive platform for academic text annotation with collaborative features and advanced export capabilities.
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          {mode === 'login' ? (
            <LoginForm
              onSuccess={handleAuthSuccess}
              onSwitchToRegister={() => setMode('register')}
            />
          ) : (
            <RegisterForm
              onSuccess={handleAuthSuccess}
              onSwitchToLogin={() => setMode('login')}
            />
          )}
        </div>

        <div className="text-center">
          <div className="text-xs text-gray-500 space-y-1">
            <p>• Multi-user annotation support</p>
            <p>• Project-based organization</p>
            <p>• Export to multiple formats</p>
            <p>• Advanced text highlighting</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
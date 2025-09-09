import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import Header from '@/components/common/Header';
import Loading from '@/components/common/Loading';

// Lazy load pages for better performance
const LoginPage = React.lazy(() => import('@/pages/LoginPage'));
const DashboardPage = React.lazy(() => import('@/pages/DashboardPage'));
const ProjectPage = React.lazy(() => import('@/pages/ProjectPage'));
const AnnotationPage = React.lazy(() => import('@/pages/AnnotationPage'));
const ProfilePage = React.lazy(() => import('@/pages/ProfilePage'));

// Project Management Pages
const ProjectsPage = React.lazy(() => import('@/pages/projects/ProjectsPage'));
const CreateProjectPage = React.lazy(() => import('@/pages/projects/CreateProjectPage'));

// Text Management Pages
const TextsPage = React.lazy(() => import('@/pages/texts/TextsPage'));
const TextUploadPage = React.lazy(() => import('@/pages/texts/TextUploadPage'));
const TextView = React.lazy(() => import('@/pages/texts/TextView'));

// Export Pages
const ExportPage = React.lazy(() => import('@/pages/export/ExportPage'));
const ExportProgress = React.lazy(() => import('@/pages/export/ExportProgress'));

// Protected Route Component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();

  if (state.isLoading) {
    return <Loading fullScreen text="Loading your session..." />;
  }

  if (!state.isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// Public Route Component (redirect if authenticated)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();

  if (state.isLoading) {
    return <Loading fullScreen text="Loading..." />;
  }

  if (state.isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

// App Layout Component
function AppLayout({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}

// Main App Router
function AppRouter() {
  return (
    <Router>
      <React.Suspense fallback={<Loading fullScreen text="Loading page..." />}>
        <Routes>
          {/* Public Routes */}
          <Route 
            path="/login" 
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            } 
          />

          {/* Protected Routes */}
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <DashboardPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Project Routes */}
          <Route 
            path="/projects" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ProjectsPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/create" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <CreateProjectPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/:projectId" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ProjectPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Text Routes */}
          <Route 
            path="/projects/:projectId/texts" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <TextsPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/:projectId/texts/upload" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <TextUploadPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/:projectId/texts/:textId/view" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <TextView />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/:projectId/texts/:textId/annotate" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <AnnotationPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Export Routes */}
          <Route 
            path="/projects/:projectId/export" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ExportPage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/projects/:projectId/export/:exportId/progress" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ExportProgress />
                </AppLayout>
              </ProtectedRoute>
            } 
          />
          
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ProfilePage />
                </AppLayout>
              </ProtectedRoute>
            } 
          />

          {/* Redirect root to dashboard if authenticated, login otherwise */}
          <Route 
            path="/" 
            element={
              <Navigate to="/dashboard" replace />
            } 
          />

          {/* 404 Route */}
          <Route 
            path="*" 
            element={
              <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                  <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
                  <p className="text-gray-600 mb-6">Page not found</p>
                  <button 
                    onClick={() => window.history.back()}
                    className="btn btn-primary btn-md"
                  >
                    Go Back
                  </button>
                </div>
              </div>
            } 
          />
        </Routes>
      </React.Suspense>
    </Router>
  );
}

// Main App Component
function App() {
  return (
    <AuthProvider>
      <AppRouter />
      <Toaster 
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
    </AuthProvider>
  );
}

export default App;
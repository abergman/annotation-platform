import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  DocumentIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { ExportJob } from '@/types/api';
import Loading from '@/components/common/Loading';

interface ExportProgressProps {}

export function ExportProgress({}: ExportProgressProps) {
  const { projectId, exportId } = useParams<{ projectId: string; exportId: string }>();
  const navigate = useNavigate();
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchExportJob = async () => {
      if (!exportId) return;

      try {
        setLoading(true);
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Mock export job data
        const mockExportJob: ExportJob = {
          id: exportId,
          project_id: projectId!,
          created_by: 'current-user',
          options: {
            format: 'json',
            include_metadata: true,
            include_confidence: true,
            include_notes: true,
            filter_by_user: [],
            filter_by_label: []
          },
          status: 'processing',
          progress: 0,
          created_at: new Date().toISOString()
        };

        setExportJob(mockExportJob);
      } catch (err) {
        console.error('Error fetching export job:', err);
        setError('Failed to load export job');
      } finally {
        setLoading(false);
      }
    };

    fetchExportJob();
  }, [exportId, projectId]);

  // Simulate progress updates
  useEffect(() => {
    if (!exportJob || exportJob.status === 'completed' || exportJob.status === 'failed') {
      return;
    }

    const interval = setInterval(() => {
      setExportJob(prev => {
        if (!prev || prev.status === 'completed' || prev.status === 'failed') {
          return prev;
        }

        const newProgress = Math.min(prev.progress + Math.random() * 15, 100);
        
        // Simulate completion or failure
        if (newProgress >= 100) {
          const success = Math.random() > 0.1; // 90% success rate
          
          if (success) {
            toast.success('Export completed successfully!');
            return {
              ...prev,
              status: 'completed',
              progress: 100,
              completed_at: new Date().toISOString(),
              download_url: `/exports/annotations-${Date.now()}.${prev.options.format}`
            };
          } else {
            toast.error('Export failed');
            return {
              ...prev,
              status: 'failed',
              progress: 100,
              error_message: 'Export failed due to processing error'
            };
          }
        }

        return {
          ...prev,
          progress: newProgress
        };
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [exportJob?.status]);

  const handleDownload = () => {
    if (exportJob?.download_url) {
      // In a real app, this would trigger the download
      window.open(exportJob.download_url, '_blank');
      toast.success('Download started');
    }
  };

  const handleRetry = () => {
    if (exportJob) {
      setExportJob({
        ...exportJob,
        status: 'processing',
        progress: 0,
        error_message: undefined,
        completed_at: undefined,
        download_url: undefined
      });
      toast.info('Retrying export...');
    }
  };

  const getStatusInfo = (status: ExportJob['status']) => {
    switch (status) {
      case 'pending':
        return {
          icon: ClockIcon,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-100',
          message: 'Export job is queued'
        };
      case 'processing':
        return {
          icon: DocumentIcon,
          color: 'text-blue-600',
          bgColor: 'bg-blue-100',
          message: 'Processing annotations...'
        };
      case 'completed':
        return {
          icon: CheckCircleIcon,
          color: 'text-green-600',
          bgColor: 'bg-green-100',
          message: 'Export completed successfully'
        };
      case 'failed':
        return {
          icon: ExclamationCircleIcon,
          color: 'text-red-600',
          bgColor: 'bg-red-100',
          message: 'Export failed'
        };
      default:
        return {
          icon: ClockIcon,
          color: 'text-gray-600',
          bgColor: 'bg-gray-100',
          message: 'Unknown status'
        };
    }
  };

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const diffMs = end.getTime() - start.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    
    if (diffSecs < 60) {
      return `${diffSecs} seconds`;
    } else if (diffSecs < 3600) {
      const minutes = Math.floor(diffSecs / 60);
      const seconds = diffSecs % 60;
      return `${minutes}m ${seconds}s`;
    } else {
      const hours = Math.floor(diffSecs / 3600);
      const minutes = Math.floor((diffSecs % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  };

  if (loading) {
    return <Loading fullScreen text="Loading export job..." />;
  }

  if (error || !exportJob) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <ExclamationCircleIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900">
            {error || 'Export job not found'}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            The export job you're looking for doesn't exist or you don't have access to it.
          </p>
          <div className="mt-6">
            <button
              onClick={() => navigate(`/projects/${projectId}/export`)}
              className="btn btn-primary"
            >
              Back to Export
            </button>
          </div>
        </div>
      </div>
    );
  }

  const statusInfo = getStatusInfo(exportJob.status);
  const StatusIcon = statusInfo.icon;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate(`/projects/${projectId}/export`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Export
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Export Progress</h1>
        <p className="mt-2 text-gray-600">
          Track the progress of your annotation export
        </p>
      </div>

      {/* Progress Card */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-8">
        <div className="px-8 py-8">
          {/* Status Header */}
          <div className="flex items-center justify-center mb-8">
            <div className={`p-4 rounded-full ${statusInfo.bgColor}`}>
              <StatusIcon className={`h-12 w-12 ${statusInfo.color}`} />
            </div>
          </div>

          {/* Status Message */}
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {statusInfo.message}
            </h2>
            <p className="text-gray-600">
              Export started {formatDuration(exportJob.created_at, exportJob.completed_at)} ago
            </p>
          </div>

          {/* Progress Bar */}
          <div className="mb-8">
            <div className="flex justify-between text-sm font-medium text-gray-700 mb-2">
              <span>Progress</span>
              <span>{Math.round(exportJob.progress)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className={`h-3 rounded-full transition-all duration-500 ease-out ${
                  exportJob.status === 'completed' 
                    ? 'bg-green-500'
                    : exportJob.status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${exportJob.progress}%` }}
              />
            </div>
          </div>

          {/* Error Message */}
          {exportJob.error_message && (
            <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex">
                <ExclamationCircleIcon className="h-5 w-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
                <div className="text-sm text-red-700">
                  <p className="font-medium mb-1">Export Failed</p>
                  <p>{exportJob.error_message}</p>
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-center space-x-4">
            {exportJob.status === 'completed' && exportJob.download_url && (
              <button
                onClick={handleDownload}
                className="btn btn-primary btn-lg"
              >
                <ArrowDownTrayIcon className="h-5 w-5 mr-2" />
                Download Export
              </button>
            )}
            
            {exportJob.status === 'failed' && (
              <button
                onClick={handleRetry}
                className="btn btn-primary btn-lg"
              >
                Retry Export
              </button>
            )}

            <button
              onClick={() => navigate(`/projects/${projectId}/export`)}
              className="btn btn-secondary btn-lg"
            >
              Start New Export
            </button>
          </div>
        </div>
      </div>

      {/* Export Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Export Configuration */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Export Configuration</h3>
          </div>
          <div className="px-6 py-6 space-y-4">
            <div className="flex justify-between">
              <span className="text-sm font-medium text-gray-700">Format</span>
              <span className="text-sm text-gray-900 uppercase font-mono">
                {exportJob.options.format}
              </span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-sm font-medium text-gray-700">Include Metadata</span>
              <span className="text-sm text-gray-900">
                {exportJob.options.include_metadata ? 'Yes' : 'No'}
              </span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-sm font-medium text-gray-700">Include Confidence</span>
              <span className="text-sm text-gray-900">
                {exportJob.options.include_confidence ? 'Yes' : 'No'}
              </span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-sm font-medium text-gray-700">Include Notes</span>
              <span className="text-sm text-gray-900">
                {exportJob.options.include_notes ? 'Yes' : 'No'}
              </span>
            </div>

            {exportJob.options.filter_by_user && exportJob.options.filter_by_user.length > 0 && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">User Filter</span>
                <span className="text-sm text-gray-900">
                  {exportJob.options.filter_by_user.length} user(s) selected
                </span>
              </div>
            )}

            {exportJob.options.filter_by_label && exportJob.options.filter_by_label.length > 0 && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">Label Filter</span>
                <span className="text-sm text-gray-900">
                  {exportJob.options.filter_by_label.length} label(s) selected
                </span>
              </div>
            )}

            {exportJob.options.date_range && (
              <div>
                <span className="text-sm font-medium text-gray-700 block mb-1">Date Range</span>
                <span className="text-sm text-gray-900">
                  {exportJob.options.date_range.start} to {exportJob.options.date_range.end}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Export Timeline */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Timeline</h3>
          </div>
          <div className="px-6 py-6">
            <div className="flow-root">
              <ul className="-mb-8">
                <li>
                  <div className="relative pb-8">
                    <div className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"></div>
                    <div className="relative flex space-x-3">
                      <div>
                        <span className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center ring-8 ring-white">
                          <ClockIcon className="h-4 w-4 text-white" />
                        </span>
                      </div>
                      <div className="min-w-0 flex-1 pt-1.5">
                        <div>
                          <p className="text-sm text-gray-500">
                            Export job created
                          </p>
                          <p className="text-xs text-gray-400">
                            {new Date(exportJob.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </li>

                {exportJob.status !== 'pending' && (
                  <li>
                    <div className="relative pb-8">
                      {exportJob.status !== 'processing' && (
                        <div className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"></div>
                      )}
                      <div className="relative flex space-x-3">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-yellow-500 flex items-center justify-center ring-8 ring-white">
                            <DocumentIcon className="h-4 w-4 text-white" />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5">
                          <div>
                            <p className="text-sm text-gray-500">
                              Processing started
                            </p>
                            <p className="text-xs text-gray-400">
                              {new Date(exportJob.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                )}

                {exportJob.status === 'completed' && (
                  <li>
                    <div className="relative">
                      <div className="relative flex space-x-3">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-green-500 flex items-center justify-center ring-8 ring-white">
                            <CheckCircleIcon className="h-4 w-4 text-white" />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5">
                          <div>
                            <p className="text-sm text-gray-500">
                              Export completed
                            </p>
                            {exportJob.completed_at && (
                              <p className="text-xs text-gray-400">
                                {new Date(exportJob.completed_at).toLocaleString()}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                )}

                {exportJob.status === 'failed' && (
                  <li>
                    <div className="relative">
                      <div className="relative flex space-x-3">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-red-500 flex items-center justify-center ring-8 ring-white">
                            <ExclamationCircleIcon className="h-4 w-4 text-white" />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5">
                          <div>
                            <p className="text-sm text-gray-500">
                              Export failed
                            </p>
                            <p className="text-xs text-gray-400">
                              {new Date().toLocaleString()}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Help Info */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex">
          <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-700">
            <p className="font-medium mb-2">Export Process</p>
            <ul className="space-y-1">
              <li>• The system is processing your annotations and applying filters</li>
              <li>• Large datasets may take several minutes to export</li>
              <li>• You'll be able to download the file once processing is complete</li>
              <li>• Export files are available for download for 7 days</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExportProgress;
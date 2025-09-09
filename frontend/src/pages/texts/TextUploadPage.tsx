import React, { useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowUpTrayIcon, 
  DocumentIcon, 
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowLeftIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { Text, UploadProgress } from '@/types/api';

interface TextUploadPageProps {}

interface FileUpload {
  id: string;
  file: File;
  progress: UploadProgress;
  preview?: string;
}

const ACCEPTED_FILE_TYPES = [
  'text/plain',
  'text/csv',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
];

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES = 20;

export function TextUploadPage({}: TextUploadPageProps) {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<FileUpload[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);

  const createFilePreview = async (file: File): Promise<string> => {
    if (file.type === 'text/plain' || file.type === 'text/csv') {
      const text = await file.text();
      return text.substring(0, 300);
    }
    return `${file.type} file (${formatFileSize(file.size)})`;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
      return 'File type not supported';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File size exceeds 10MB limit';
    }
    if (uploads.some(upload => upload.file.name === file.name)) {
      return 'File already added';
    }
    return null;
  };

  const addFiles = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    
    if (uploads.length + fileArray.length > MAX_FILES) {
      toast.error(`Cannot upload more than ${MAX_FILES} files at once`);
      return;
    }

    const validFiles: FileUpload[] = [];
    
    for (const file of fileArray) {
      const error = validateFile(file);
      if (error) {
        toast.error(`${file.name}: ${error}`);
        continue;
      }

      const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
      const preview = await createFilePreview(file);
      
      validFiles.push({
        id,
        file,
        preview,
        progress: {
          id,
          file_name: file.name,
          progress: 0,
          status: 'uploading'
        }
      });
    }

    if (validFiles.length > 0) {
      setUploads(prev => [...prev, ...validFiles]);
      toast.success(`Added ${validFiles.length} file(s) for upload`);
    }
  };

  const removeFile = (id: string) => {
    setUploads(prev => prev.filter(upload => upload.id !== id));
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await addFiles(e.dataTransfer.files);
    }
  }, [uploads]);

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await addFiles(e.target.files);
      // Reset input so same file can be selected again
      e.target.value = '';
    }
  };

  const simulateUpload = (upload: FileUpload): Promise<void> => {
    return new Promise((resolve, reject) => {
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 15;
        
        if (progress >= 100) {
          clearInterval(interval);
          
          // Simulate random success/failure
          const success = Math.random() > 0.1; // 90% success rate
          
          setUploads(prev => 
            prev.map(u => 
              u.id === upload.id 
                ? {
                    ...u,
                    progress: {
                      ...u.progress,
                      progress: 100,
                      status: success ? 'completed' : 'failed',
                      error_message: success ? undefined : 'Upload failed due to network error'
                    }
                  }
                : u
            )
          );
          
          if (success) {
            resolve();
          } else {
            reject(new Error('Upload failed'));
          }
        } else {
          setUploads(prev => 
            prev.map(u => 
              u.id === upload.id 
                ? {
                    ...u,
                    progress: {
                      ...u.progress,
                      progress: Math.min(progress, 100)
                    }
                  }
                : u
            )
          );
        }
      }, 200);
    });
  };

  const startUpload = async () => {
    if (uploads.length === 0) {
      toast.error('No files to upload');
      return;
    }

    setUploading(true);
    
    try {
      const uploadPromises = uploads.map(upload => simulateUpload(upload));
      await Promise.allSettled(uploadPromises);
      
      const completed = uploads.filter(u => u.progress.status === 'completed').length;
      const failed = uploads.filter(u => u.progress.status === 'failed').length;
      
      if (completed > 0) {
        toast.success(`Successfully uploaded ${completed} file(s)`);
      }
      if (failed > 0) {
        toast.error(`Failed to upload ${failed} file(s)`);
      }
      
      // Navigate back after a short delay to show results
      setTimeout(() => {
        navigate(`/projects/${projectId}/texts`);
      }, 2000);
      
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Upload process encountered errors');
    } finally {
      setUploading(false);
    }
  };

  const getStatusIcon = (status: UploadProgress['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <ExclamationCircleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <DocumentIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: UploadProgress['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-blue-500';
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate(`/projects/${projectId}/texts`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Texts
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Upload Texts</h1>
        <p className="mt-2 text-gray-600">
          Upload text files to your project for annotation
        </p>
      </div>

      {/* File Upload Area */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
        <div
          className={`p-8 border-2 border-dashed rounded-lg transition-colors ${
            dragActive 
              ? 'border-primary-500 bg-primary-50' 
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="text-center">
            <ArrowUpTrayIcon className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4">
              <label htmlFor="file-upload" className="cursor-pointer">
                <span className="mt-2 block text-sm font-semibold text-gray-900">
                  Drop files here or click to browse
                </span>
                <input
                  ref={fileInputRef}
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  multiple
                  accept=".txt,.csv,.pdf,.doc,.docx"
                  className="sr-only"
                  onChange={handleFileInput}
                />
              </label>
              <p className="mt-1 text-sm text-gray-600">
                Support for TXT, CSV, PDF, DOC, DOCX files up to 10MB each
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
        <div className="flex">
          <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-700">
            <p className="font-medium mb-1">Upload Guidelines:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Maximum file size: 10MB</li>
              <li>Maximum {MAX_FILES} files per upload batch</li>
              <li>Supported formats: TXT, CSV, PDF, DOC, DOCX</li>
              <li>Files will be processed after upload for annotation readiness</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Upload Queue */}
      {uploads.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Upload Queue ({uploads.length} files)
              </h2>
              {!uploading && (
                <button
                  onClick={() => setUploads([])}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Clear All
                </button>
              )}
            </div>
          </div>
          
          <div className="divide-y divide-gray-200">
            {uploads.map((upload) => (
              <div key={upload.id} className="px-6 py-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(upload.progress.status)}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {upload.file.name}
                      </p>
                      <p className="text-sm text-gray-500">
                        {formatFileSize(upload.file.size)} • {upload.file.type}
                      </p>
                    </div>
                  </div>
                  
                  {!uploading && upload.progress.status === 'uploading' && (
                    <button
                      onClick={() => removeFile(upload.id)}
                      className="p-1 rounded-full hover:bg-gray-100 transition-colors"
                    >
                      <XMarkIcon className="h-4 w-4 text-gray-400" />
                    </button>
                  )}
                </div>

                {/* Progress Bar */}
                <div className="mb-3">
                  <div className="flex justify-between text-sm text-gray-600 mb-1">
                    <span>
                      {upload.progress.status === 'completed' && 'Completed'}
                      {upload.progress.status === 'failed' && 'Failed'}
                      {upload.progress.status === 'uploading' && 
                        (uploading ? `Uploading... ${Math.round(upload.progress.progress)}%` : 'Pending')
                      }
                    </span>
                    <span>{Math.round(upload.progress.progress)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-200 ${getStatusColor(upload.progress.status)}`}
                      style={{ width: `${upload.progress.progress}%` }}
                    />
                  </div>
                </div>

                {/* Error Message */}
                {upload.progress.error_message && (
                  <p className="text-sm text-red-600">
                    {upload.progress.error_message}
                  </p>
                )}

                {/* Preview */}
                {upload.preview && upload.progress.status === 'uploading' && (
                  <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-600">
                    <p className="font-medium mb-1">Preview:</p>
                    <p className="line-clamp-3">{upload.preview}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {uploads.length > 0 && (
        <div className="flex items-center justify-end space-x-4">
          <button
            onClick={() => navigate(`/projects/${projectId}/texts`)}
            className="btn btn-secondary"
            disabled={uploading}
          >
            Cancel
          </button>
          <button
            onClick={startUpload}
            disabled={uploading || uploads.length === 0}
            className="btn btn-primary"
          >
            {uploading ? (
              <>
                <div className="inline-flex items-center">
                  <div className="animate-spin -ml-1 mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                  Uploading...
                </div>
              </>
            ) : (
              <>
                <ArrowUpTrayIcon className="h-5 w-5 mr-2" />
                Upload {uploads.length} Files
              </>
            )}
          </button>
        </div>
      )}

      {/* Empty State */}
      {uploads.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-500">
            No files selected. Use the upload area above to add files.
          </p>
        </div>
      )}
    </div>
  );
}

export default TextUploadPage;
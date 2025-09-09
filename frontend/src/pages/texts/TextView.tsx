import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ArrowLeftIcon, 
  EyeIcon, 
  DocumentTextIcon,
  ClockIcon,
  UserIcon,
  TagIcon,
  PencilIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import { Text, Annotation, Project } from '@/types/api';
import Loading from '@/components/common/Loading';

interface TextViewProps {}

interface AnnotationDisplayProps {
  annotation: Annotation;
  textContent: string;
  onAnnotationClick: (annotation: Annotation) => void;
}

function AnnotationDisplay({ annotation, textContent, onAnnotationClick }: AnnotationDisplayProps) {
  const before = textContent.substring(0, annotation.start_offset);
  const annotatedText = textContent.substring(annotation.start_offset, annotation.end_offset);
  const after = textContent.substring(annotation.end_offset);

  return (
    <div className="mb-4">
      <div className="text-sm text-gray-600 mb-2">
        <span className="font-medium">{annotation.label.name}</span> • 
        <span className="ml-1">
          Characters {annotation.start_offset}-{annotation.end_offset}
        </span>
        {annotation.confidence && (
          <span className="ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded">
            {Math.round(annotation.confidence * 100)}% confidence
          </span>
        )}
      </div>
      
      <div className="bg-gray-50 p-4 rounded-lg border">
        <div className="text-sm font-mono leading-relaxed">
          <span className="text-gray-600">{before}</span>
          <span 
            className="bg-yellow-200 px-1 py-0.5 rounded cursor-pointer hover:bg-yellow-300 transition-colors"
            style={{ backgroundColor: annotation.label.color + '40' }}
            onClick={() => onAnnotationClick(annotation)}
          >
            {annotatedText}
          </span>
          <span className="text-gray-600">{after}</span>
        </div>
      </div>

      {annotation.notes && (
        <div className="mt-2 text-sm text-gray-600 bg-blue-50 p-3 rounded">
          <div className="font-medium text-blue-900 mb-1">Notes:</div>
          {annotation.notes}
        </div>
      )}
    </div>
  );
}

export function TextView({}: TextViewProps) {
  const { projectId, textId } = useParams<{ projectId: string; textId: string }>();
  const navigate = useNavigate();
  const [text, setText] = useState<Text | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAnnotation, setSelectedAnnotation] = useState<Annotation | null>(null);
  const [viewMode, setViewMode] = useState<'clean' | 'highlighted'>('clean');

  useEffect(() => {
    const fetchData = async () => {
      if (!projectId || !textId) return;

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
              labels: [
                {
                  id: '1',
                  name: 'Disease',
                  color: '#ef4444',
                  description: 'Disease mentions'
                },
                {
                  id: '2',
                  name: 'Treatment',
                  color: '#10b981',
                  description: 'Treatment procedures'
                },
                {
                  id: '3',
                  name: 'Symptom',
                  color: '#f59e0b',
                  description: 'Symptom descriptions'
                }
              ]
            }
          }
        };

        // Mock text data
        const mockText: Text = {
          id: textId,
          title: 'Clinical Trial Report #1',
          content: `Cardiovascular diseases remain the leading cause of mortality worldwide. Recent clinical trials have demonstrated the efficacy of novel therapeutic interventions in reducing myocardial infarction rates.

The study enrolled 2,847 patients with documented coronary artery disease. Participants were randomly assigned to receive either the experimental drug (atorvastatin 80mg daily) or placebo. Primary endpoints included cardiovascular death, non-fatal myocardial infarction, and stroke.

Results showed a significant 23% reduction in major adverse cardiovascular events in the treatment group (p<0.001). Common side effects included muscle pain, fatigue, and mild elevation in liver enzymes. However, serious adverse events were rare and comparable between groups.

The intervention demonstrated superior efficacy compared to standard care. Patients receiving the treatment showed improved lipid profiles, with LDL cholesterol levels decreasing by an average of 45%. Additionally, inflammatory markers such as C-reactive protein were significantly reduced.

In conclusion, this large-scale randomized controlled trial provides compelling evidence for the cardiovascular benefits of high-intensity statin therapy. The findings support current clinical guidelines recommending aggressive lipid management in high-risk patients.`,
          project_id: projectId,
          uploaded_at: '2023-12-10T10:00:00Z',
          uploaded_by: 'researcher1',
          status: 'ready',
          annotations_count: 8,
          file_name: 'clinical_trial_001.txt',
          file_size: 1456,
          metadata: { source: 'clinical_database', study_id: 'CT-2023-001' }
        };

        // Mock annotations data
        const mockAnnotations: Annotation[] = [
          {
            id: '1',
            text_id: textId,
            user_id: 'annotator1',
            start_offset: 0,
            end_offset: 22,
            selected_text: 'Cardiovascular diseases',
            label: mockProject.settings.label_schema.labels[0],
            confidence: 0.95,
            notes: 'Primary focus of the study',
            created_at: '2023-12-11T09:00:00Z',
            updated_at: '2023-12-11T09:00:00Z'
          },
          {
            id: '2',
            text_id: textId,
            user_id: 'annotator1',
            start_offset: 173,
            end_offset: 197,
            selected_text: 'therapeutic interventions',
            label: mockProject.settings.label_schema.labels[1],
            confidence: 0.87,
            created_at: '2023-12-11T09:15:00Z',
            updated_at: '2023-12-11T09:15:00Z'
          },
          {
            id: '3',
            text_id: textId,
            user_id: 'annotator2',
            start_offset: 209,
            end_offset: 228,
            selected_text: 'myocardial infarction',
            label: mockProject.settings.label_schema.labels[0],
            confidence: 0.98,
            notes: 'Also known as heart attack',
            created_at: '2023-12-11T10:30:00Z',
            updated_at: '2023-12-11T10:30:00Z'
          },
          {
            id: '4',
            text_id: textId,
            user_id: 'annotator1',
            start_offset: 372,
            end_offset: 393,
            selected_text: 'atorvastatin 80mg daily',
            label: mockProject.settings.label_schema.labels[1],
            confidence: 0.92,
            created_at: '2023-12-11T11:00:00Z',
            updated_at: '2023-12-11T11:00:00Z'
          },
          {
            id: '5',
            text_id: textId,
            user_id: 'annotator2',
            start_offset: 697,
            end_offset: 708,
            selected_text: 'muscle pain',
            label: mockProject.settings.label_schema.labels[2],
            confidence: 0.89,
            created_at: '2023-12-11T14:20:00Z',
            updated_at: '2023-12-11T14:20:00Z'
          },
          {
            id: '6',
            text_id: textId,
            user_id: 'annotator2',
            start_offset: 710,
            end_offset: 717,
            selected_text: 'fatigue',
            label: mockProject.settings.label_schema.labels[2],
            confidence: 0.91,
            created_at: '2023-12-11T14:25:00Z',
            updated_at: '2023-12-11T14:25:00Z'
          }
        ];

        setProject(mockProject);
        setText(mockText);
        setAnnotations(mockAnnotations);
        setError(null);
      } catch (err) {
        console.error('Error fetching text:', err);
        setError('Failed to load text');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId, textId]);

  const handleAnnotationClick = (annotation: Annotation) => {
    setSelectedAnnotation(annotation);
  };

  const renderHighlightedText = () => {
    if (!text || annotations.length === 0) {
      return <div className="whitespace-pre-wrap">{text?.content}</div>;
    }

    // Sort annotations by start offset
    const sortedAnnotations = [...annotations].sort((a, b) => a.start_offset - b.start_offset);
    const segments = [];
    let lastOffset = 0;

    sortedAnnotations.forEach((annotation, index) => {
      // Add text before annotation
      if (annotation.start_offset > lastOffset) {
        segments.push(
          <span key={`text-${index}`}>
            {text.content.substring(lastOffset, annotation.start_offset)}
          </span>
        );
      }

      // Add highlighted annotation
      segments.push(
        <span
          key={`annotation-${annotation.id}`}
          className="cursor-pointer px-1 py-0.5 rounded hover:opacity-80 transition-opacity"
          style={{ 
            backgroundColor: annotation.label.color + '60',
            borderBottom: `2px solid ${annotation.label.color}`
          }}
          onClick={() => handleAnnotationClick(annotation)}
          title={`${annotation.label.name}: ${annotation.selected_text}`}
        >
          {annotation.selected_text}
        </span>
      );

      lastOffset = annotation.end_offset;
    });

    // Add remaining text
    if (lastOffset < text.content.length) {
      segments.push(
        <span key="text-end">
          {text.content.substring(lastOffset)}
        </span>
      );
    }

    return <div className="whitespace-pre-wrap leading-relaxed">{segments}</div>;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  if (loading) {
    return <Loading fullScreen text="Loading text..." />;
  }

  if (error || !text || !project) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900">
            {error || 'Text not found'}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            The text you're looking for doesn't exist or you don't have access to it.
          </p>
          <div className="mt-6">
            <Link to={`/projects/${projectId}/texts`} className="btn btn-primary">
              Back to Texts
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
          onClick={() => navigate(`/projects/${projectId}/texts`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-2" />
          Back to Texts
        </button>
        
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{text.title}</h1>
            <p className="mt-2 text-gray-600">
              {text.file_name} • {formatFileSize(text.file_size)}
            </p>
          </div>
          <div className="mt-4 sm:mt-0 flex space-x-3">
            <Link
              to={`/projects/${projectId}/texts/${textId}/annotate`}
              className="btn btn-primary"
            >
              <PencilIcon className="h-5 w-5 mr-2" />
              Annotate
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-3">
          {/* Text Display Controls */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Text Content</h2>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setViewMode('clean')}
                    className={`btn btn-sm ${
                      viewMode === 'clean' ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    <EyeIcon className="h-4 w-4 mr-1" />
                    Clean
                  </button>
                  <button
                    onClick={() => setViewMode('highlighted')}
                    className={`btn btn-sm ${
                      viewMode === 'highlighted' ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    <TagIcon className="h-4 w-4 mr-1" />
                    Highlighted
                  </button>
                </div>
              </div>
            </div>
            
            <div className="px-6 py-6">
              <div className="prose max-w-none text-gray-900 font-mono text-sm">
                {viewMode === 'clean' ? (
                  <div className="whitespace-pre-wrap leading-relaxed">
                    {text.content}
                  </div>
                ) : (
                  renderHighlightedText()
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          {/* Text Metadata */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900">Text Information</h3>
            </div>
            <div className="px-4 py-4 space-y-4">
              <div className="flex items-start space-x-3">
                <DocumentTextIcon className="h-5 w-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">Status</p>
                  <p className="text-sm text-gray-600 capitalize">{text.status}</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <ClockIcon className="h-5 w-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">Uploaded</p>
                  <p className="text-sm text-gray-600">
                    {new Date(text.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <UserIcon className="h-5 w-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">Uploaded by</p>
                  <p className="text-sm text-gray-600">{text.uploaded_by}</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <TagIcon className="h-5 w-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">Annotations</p>
                  <p className="text-sm text-gray-600">{annotations.length} total</p>
                </div>
              </div>
            </div>
          </div>

          {/* Annotations List */}
          {annotations.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
              <div className="px-4 py-3 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900">
                  Annotations ({annotations.length})
                </h3>
              </div>
              <div className="px-4 py-4">
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {annotations.map((annotation) => (
                    <div
                      key={annotation.id}
                      className={`p-3 rounded-lg border-l-4 cursor-pointer transition-colors ${
                        selectedAnnotation?.id === annotation.id
                          ? 'bg-blue-50 border-blue-500'
                          : 'bg-gray-50 border-gray-300 hover:bg-gray-100'
                      }`}
                      style={{ borderLeftColor: annotation.label.color }}
                      onClick={() => handleAnnotationClick(annotation)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span 
                          className="text-xs font-medium px-2 py-1 rounded text-white"
                          style={{ backgroundColor: annotation.label.color }}
                        >
                          {annotation.label.name}
                        </span>
                        {annotation.confidence && (
                          <span className="text-xs text-gray-500">
                            {Math.round(annotation.confidence * 100)}%
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-900 font-medium mb-1">
                        "{annotation.selected_text}"
                      </p>
                      <p className="text-xs text-gray-500">
                        Characters {annotation.start_offset}-{annotation.end_offset}
                      </p>
                      {annotation.notes && (
                        <p className="text-xs text-gray-600 mt-2 italic">
                          {annotation.notes}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Help Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5 mr-3 flex-shrink-0" />
              <div className="text-sm text-blue-700">
                <p className="font-medium mb-1">Viewing Tips:</p>
                <ul className="text-xs space-y-1">
                  <li>• Switch between clean and highlighted view</li>
                  <li>• Click annotations to see details</li>
                  <li>• Use the annotate button to add new annotations</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Selected Annotation Details Modal/Panel */}
      {selectedAnnotation && (
        <div className="fixed inset-0 z-50 overflow-y-auto" onClick={() => setSelectedAnnotation(null)}>
          <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"></div>
            
            <div 
              className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center">
                    <span 
                      className="text-sm font-medium px-3 py-1 rounded text-white mr-3"
                      style={{ backgroundColor: selectedAnnotation.label.color }}
                    >
                      {selectedAnnotation.label.name}
                    </span>
                    {selectedAnnotation.confidence && (
                      <span className="text-sm text-gray-500">
                        {Math.round(selectedAnnotation.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => setSelectedAnnotation(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ×
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Selected Text</h4>
                    <p className="text-sm bg-gray-100 p-3 rounded">
                      "{selectedAnnotation.selected_text}"
                    </p>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Position</h4>
                    <p className="text-sm text-gray-600">
                      Characters {selectedAnnotation.start_offset} to {selectedAnnotation.end_offset}
                    </p>
                  </div>

                  {selectedAnnotation.notes && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Notes</h4>
                      <p className="text-sm text-gray-600 bg-blue-50 p-3 rounded">
                        {selectedAnnotation.notes}
                      </p>
                    </div>
                  )}

                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Created</h4>
                    <p className="text-sm text-gray-600">
                      {new Date(selectedAnnotation.created_at).toLocaleString()} by {selectedAnnotation.user_id}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TextView;
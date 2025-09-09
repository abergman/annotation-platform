import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { Annotation, Label, TextDocument, AnnotationFilter, SelectionRange } from '../types/annotation';

interface AnnotationContextValue {
  // Current document and annotations
  currentDocument: TextDocument | null;
  setCurrentDocument: (doc: TextDocument) => void;
  annotations: Annotation[];
  setAnnotations: React.Dispatch<React.SetStateAction<Annotation[]>>;
  
  // Labels
  labels: Label[];
  setLabels: React.Dispatch<React.SetStateAction<Label[]>>;
  
  // Text selection
  currentSelection: SelectionRange | null;
  setCurrentSelection: (selection: SelectionRange | null) => void;
  
  // Annotation management
  createAnnotation: (annotation: Omit<Annotation, 'id' | 'createdAt' | 'updatedAt'>) => void;
  updateAnnotation: (id: string, updates: Partial<Annotation>) => void;
  deleteAnnotation: (id: string) => void;
  
  // Filtering and search
  filter: AnnotationFilter;
  setFilter: React.Dispatch<React.SetStateAction<AnnotationFilter>>;
  filteredAnnotations: Annotation[];
  
  // UI state
  selectedAnnotationId: string | null;
  setSelectedAnnotationId: (id: string | null) => void;
  showAnnotationCreator: boolean;
  setShowAnnotationCreator: (show: boolean) => void;
  
  // Keyboard shortcuts
  registerKeyboardShortcuts: () => void;
  unregisterKeyboardShortcuts: () => void;
}

const AnnotationContext = createContext<AnnotationContextValue | null>(null);

export const useAnnotation = () => {
  const context = useContext(AnnotationContext);
  if (!context) {
    throw new Error('useAnnotation must be used within an AnnotationProvider');
  }
  return context;
};

interface AnnotationProviderProps {
  children: React.ReactNode;
}

export const AnnotationProvider: React.FC<AnnotationProviderProps> = ({ children }) => {
  const [currentDocument, setCurrentDocument] = useState<TextDocument | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [labels, setLabels] = useState<Label[]>([
    { id: '1', name: 'Person', color: '#3B82F6', shortcut: 'p' },
    { id: '2', name: 'Organization', color: '#EF4444', shortcut: 'o' },
    { id: '3', name: 'Location', color: '#10B981', shortcut: 'l' },
    { id: '4', name: 'Date', color: '#F59E0B', shortcut: 'd' },
    { id: '5', name: 'Event', color: '#8B5CF6', shortcut: 'e' },
  ]);
  
  const [currentSelection, setCurrentSelection] = useState<SelectionRange | null>(null);
  const [filter, setFilter] = useState<AnnotationFilter>({});
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<string | null>(null);
  const [showAnnotationCreator, setShowAnnotationCreator] = useState(false);
  
  const keyboardHandlerRef = useRef<(event: KeyboardEvent) => void>();

  // Filter annotations based on current filter
  const filteredAnnotations = annotations.filter(annotation => {
    if (filter.labels && filter.labels.length > 0) {
      if (!annotation.labels.some(label => filter.labels!.includes(label))) {
        return false;
      }
    }
    
    if (filter.status && filter.status.length > 0) {
      if (!filter.status.includes(annotation.status)) {
        return false;
      }
    }
    
    if (filter.confidence) {
      if (annotation.confidence !== undefined) {
        if (filter.confidence.min !== undefined && annotation.confidence < filter.confidence.min) {
          return false;
        }
        if (filter.confidence.max !== undefined && annotation.confidence > filter.confidence.max) {
          return false;
        }
      }
    }
    
    if (filter.createdBy && filter.createdBy.length > 0) {
      if (!filter.createdBy.includes(annotation.createdBy)) {
        return false;
      }
    }
    
    return true;
  });

  const createAnnotation = useCallback((annotationData: Omit<Annotation, 'id' | 'createdAt' | 'updatedAt'>) => {
    const newAnnotation: Annotation = {
      ...annotationData,
      id: `ann_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    
    setAnnotations(prev => [...prev, newAnnotation]);
    setShowAnnotationCreator(false);
    setCurrentSelection(null);
  }, []);

  const updateAnnotation = useCallback((id: string, updates: Partial<Annotation>) => {
    setAnnotations(prev => prev.map(ann => 
      ann.id === id 
        ? { ...ann, ...updates, updatedAt: new Date() }
        : ann
    ));
  }, []);

  const deleteAnnotation = useCallback((id: string) => {
    setAnnotations(prev => prev.filter(ann => ann.id !== id));
    if (selectedAnnotationId === id) {
      setSelectedAnnotationId(null);
    }
  }, [selectedAnnotationId]);

  const registerKeyboardShortcuts = useCallback(() => {
    const handleKeyboard = (event: KeyboardEvent) => {
      // Don't interfere with form inputs
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }

      // Escape key - close annotation creator or deselect
      if (event.key === 'Escape') {
        setShowAnnotationCreator(false);
        setSelectedAnnotationId(null);
        setCurrentSelection(null);
        return;
      }

      // Delete key - delete selected annotation
      if (event.key === 'Delete' && selectedAnnotationId) {
        deleteAnnotation(selectedAnnotationId);
        return;
      }

      // Enter key - create annotation if selection exists
      if (event.key === 'Enter' && currentSelection && !showAnnotationCreator) {
        setShowAnnotationCreator(true);
        return;
      }

      // Label shortcuts (only if selection exists or annotation creator is open)
      if ((currentSelection || showAnnotationCreator) && !event.ctrlKey && !event.altKey && !event.metaKey) {
        const label = labels.find(l => l.shortcut === event.key.toLowerCase());
        if (label && currentSelection) {
          // Quick create annotation with this label
          createAnnotation({
            textId: currentDocument?.id || '',
            startOffset: currentSelection.startOffset,
            endOffset: currentSelection.endOffset,
            text: currentSelection.text,
            labels: [label.id],
            createdBy: 'current_user', // TODO: Get from auth context
            status: 'draft',
          });
        }
      }
    };

    keyboardHandlerRef.current = handleKeyboard;
    document.addEventListener('keydown', handleKeyboard);
  }, [currentSelection, showAnnotationCreator, selectedAnnotationId, labels, currentDocument, createAnnotation, deleteAnnotation]);

  const unregisterKeyboardShortcuts = useCallback(() => {
    if (keyboardHandlerRef.current) {
      document.removeEventListener('keydown', keyboardHandlerRef.current);
    }
  }, []);

  // Auto-register keyboard shortcuts
  useEffect(() => {
    registerKeyboardShortcuts();
    return unregisterKeyboardShortcuts;
  }, [registerKeyboardShortcuts, unregisterKeyboardShortcuts]);

  const value: AnnotationContextValue = {
    currentDocument,
    setCurrentDocument,
    annotations,
    setAnnotations,
    labels,
    setLabels,
    currentSelection,
    setCurrentSelection,
    createAnnotation,
    updateAnnotation,
    deleteAnnotation,
    filter,
    setFilter,
    filteredAnnotations,
    selectedAnnotationId,
    setSelectedAnnotationId,
    showAnnotationCreator,
    setShowAnnotationCreator,
    registerKeyboardShortcuts,
    unregisterKeyboardShortcuts,
  };

  return (
    <AnnotationContext.Provider value={value}>
      {children}
    </AnnotationContext.Provider>
  );
};
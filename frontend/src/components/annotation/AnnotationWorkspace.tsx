import React, { useState, useEffect, useMemo } from 'react';
import { useAnnotation } from '../../contexts/AnnotationContext';
import { Annotation, Label, TextDocument } from '../../types/annotation';
import TextDisplay from './TextDisplay';
import AnnotationCreator from './AnnotationCreator';
import AnnotationSidebar from './AnnotationSidebar';

interface AnnotationWorkspaceProps {
  document: TextDocument;
  onDocumentChange?: (document: TextDocument) => void;
}

const AnnotationWorkspace: React.FC<AnnotationWorkspaceProps> = ({
  document,
  onDocumentChange,
}) => {
  const {
    currentDocument,
    setCurrentDocument,
    annotations,
    setAnnotations,
    labels,
    currentSelection,
    createAnnotation,
    updateAnnotation,
    deleteAnnotation,
    selectedAnnotationId,
    setSelectedAnnotationId,
    showAnnotationCreator,
    setShowAnnotationCreator,
  } = useAnnotation();

  const [editingAnnotation, setEditingAnnotation] = useState<Annotation | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false);

  // Initialize document
  useEffect(() => {
    setCurrentDocument(document);
    setAnnotations(document.annotations || []);
  }, [document, setCurrentDocument, setAnnotations]);

  // Track unsaved changes
  useEffect(() => {
    if (currentDocument && annotations !== currentDocument.annotations) {
      setHasUnsavedChanges(true);
    }
  }, [annotations, currentDocument]);

  // Handle annotation creation
  const handleCreateAnnotation = (annotationData: Omit<Annotation, 'id' | 'createdAt' | 'updatedAt'>) => {
    createAnnotation(annotationData);
    setHasUnsavedChanges(true);
  };

  // Handle annotation update
  const handleUpdateAnnotation = (id: string, updates: Partial<Annotation>) => {
    updateAnnotation(id, updates);
    setEditingAnnotation(null);
    setHasUnsavedChanges(true);
  };

  // Handle annotation deletion
  const handleDeleteAnnotation = (id: string) => {
    deleteAnnotation(id);
    setHasUnsavedChanges(true);
  };

  // Handle annotation selection from sidebar
  const handleAnnotationClick = (annotation: Annotation) => {
    setSelectedAnnotationId(annotation.id);
    // TODO: Scroll to annotation in text display
  };

  // Handle annotation edit
  const handleAnnotationEdit = (annotation: Annotation) => {
    setEditingAnnotation(annotation);
    setShowAnnotationCreator(true);
  };

  // Save annotations to document
  const handleSaveDocument = () => {
    if (currentDocument && hasUnsavedChanges) {
      const updatedDocument: TextDocument = {
        ...currentDocument,
        annotations,
        metadata: {
          ...currentDocument.metadata,
          lastSaved: new Date().toISOString(),
          annotationCount: annotations.length,
        },
      };
      
      onDocumentChange?.(updatedDocument);
      setHasUnsavedChanges(false);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Save shortcut (Ctrl+S)
      if (event.ctrlKey && event.key === 's') {
        event.preventDefault();
        handleSaveDocument();
        return;
      }

      // Help shortcut (?)
      if (event.key === '?' && !event.ctrlKey && !event.altKey && !event.metaKey) {
        setShowShortcutsHelp(!showShortcutsHelp);
        return;
      }

      // Undo/Redo (Ctrl+Z, Ctrl+Y) - TODO: Implement undo/redo
      if (event.ctrlKey && (event.key === 'z' || event.key === 'y')) {
        event.preventDefault();
        // TODO: Implement undo/redo functionality
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [hasUnsavedChanges, showShortcutsHelp]);

  // Annotation statistics
  const annotationStats = useMemo(() => {
    const stats = {
      total: annotations.length,
      byStatus: {
        draft: annotations.filter(a => a.status === 'draft').length,
        pending: annotations.filter(a => a.status === 'pending').length,
        validated: annotations.filter(a => a.status === 'validated').length,
        rejected: annotations.filter(a => a.status === 'rejected').length,
      },
      byLabel: {} as Record<string, number>,
      averageConfidence: annotations.length > 0 
        ? annotations.reduce((sum, a) => sum + (a.confidence || 0), 0) / annotations.length 
        : 0,
    };

    // Calculate label statistics
    labels.forEach(label => {
      stats.byLabel[label.name] = annotations.filter(a => a.labels.includes(label.id)).length;
    });

    return stats;
  }, [annotations, labels]);

  if (!currentDocument) {
    return (
      <div className="workspace-loading">
        <div className="loading-spinner">Loading document...</div>
      </div>
    );
  }

  return (
    <div className="annotation-workspace">
      {/* Top Bar */}
      <div className="workspace-header">
        <div className="document-info">
          <h2 className="document-title">{currentDocument.title}</h2>
          <div className="document-stats">
            <span className="stat">
              {annotationStats.total} annotations
            </span>
            <span className="stat">
              {Math.round(annotationStats.averageConfidence * 100)}% avg confidence
            </span>
            {hasUnsavedChanges && (
              <span className="unsaved-indicator">• Unsaved changes</span>
            )}
          </div>
        </div>

        <div className="workspace-actions">
          <button
            className="help-button"
            onClick={() => setShowShortcutsHelp(!showShortcutsHelp)}
            title="Show keyboard shortcuts (?)"
          >
            ?
          </button>
          
          <button
            className="save-button"
            onClick={handleSaveDocument}
            disabled={!hasUnsavedChanges}
            title="Save document (Ctrl+S)"
          >
            💾 Save
          </button>
        </div>
      </div>

      {/* Shortcuts Help */}
      {showShortcutsHelp && (
        <div className="shortcuts-help">
          <div className="shortcuts-content">
            <h3>Keyboard Shortcuts</h3>
            <div className="shortcuts-grid">
              <div className="shortcut-group">
                <h4>Text Selection</h4>
                <div className="shortcut"><span>Enter</span> Create annotation from selection</div>
                <div className="shortcut"><span>Double-click</span> Create annotation</div>
                <div className="shortcut"><span>Esc</span> Clear selection</div>
              </div>
              
              <div className="shortcut-group">
                <h4>Labels</h4>
                {labels.filter(l => l.shortcut).map(label => (
                  <div key={label.id} className="shortcut">
                    <span>{label.shortcut}</span> {label.name}
                  </div>
                ))}
              </div>
              
              <div className="shortcut-group">
                <h4>General</h4>
                <div className="shortcut"><span>Ctrl+S</span> Save document</div>
                <div className="shortcut"><span>Delete</span> Delete selected annotation</div>
                <div className="shortcut"><span>?</span> Toggle this help</div>
              </div>
            </div>
            
            <button 
              className="close-help"
              onClick={() => setShowShortcutsHelp(false)}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Main Workspace */}
      <div className="workspace-main">
        {/* Text Display Area */}
        <div className="text-area">
          <TextDisplay
            text={currentDocument.content}
            annotations={annotations}
            labels={labels}
            onAnnotationClick={handleAnnotationClick}
            onSelectionChange={(hasSelection) => {
              // Could show selection-based UI hints here
            }}
          />
        </div>

        {/* Sidebar */}
        <AnnotationSidebar
          annotations={annotations}
          labels={labels}
          onAnnotationClick={handleAnnotationClick}
          onAnnotationEdit={handleAnnotationEdit}
          onAnnotationDelete={handleDeleteAnnotation}
          selectedAnnotationId={selectedAnnotationId}
        />
      </div>

      {/* Annotation Creator Modal */}
      <AnnotationCreator
        isOpen={showAnnotationCreator}
        onClose={() => {
          setShowAnnotationCreator(false);
          setEditingAnnotation(null);
        }}
        selection={currentSelection}
        existingAnnotation={editingAnnotation || undefined}
        labels={labels}
        onSave={handleCreateAnnotation}
        onUpdate={handleUpdateAnnotation}
        onDelete={handleDeleteAnnotation}
      />

      {/* Status Bar */}
      <div className="workspace-status">
        <div className="status-left">
          {currentSelection && (
            <span className="selection-info">
              "{currentSelection.text.substring(0, 50)}
              {currentSelection.text.length > 50 ? '...' : ''}" selected
            </span>
          )}
          
          {selectedAnnotationId && (
            <span className="annotation-info">
              Annotation selected
            </span>
          )}
        </div>

        <div className="status-right">
          <div className="status-stats">
            <span>Draft: {annotationStats.byStatus.draft}</span>
            <span>Pending: {annotationStats.byStatus.pending}</span>
            <span>Validated: {annotationStats.byStatus.validated}</span>
          </div>
        </div>
      </div>

      <style jsx>{`
        .annotation-workspace {
          display: flex;
          flex-direction: column;
          height: 100vh;
          background: #ffffff;
        }

        .workspace-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          background: #f9fafb;
          border-bottom: 1px solid #e5e7eb;
        }

        .document-info h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
          color: #1f2937;
        }

        .document-stats {
          display: flex;
          gap: 16px;
          margin-top: 4px;
          font-size: 14px;
          color: #6b7280;
        }

        .stat {
          display: flex;
          align-items: center;
        }

        .unsaved-indicator {
          color: #f59e0b;
          font-weight: 500;
        }

        .workspace-actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }

        .help-button,
        .save-button {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          background: white;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .help-button {
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
        }

        .help-button:hover {
          background-color: #f3f4f6;
        }

        .save-button {
          background: #3b82f6;
          color: white;
          border-color: #3b82f6;
        }

        .save-button:hover:not(:disabled) {
          background: #2563eb;
        }

        .save-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .shortcuts-help {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .shortcuts-content {
          background: white;
          border-radius: 12px;
          padding: 24px;
          max-width: 600px;
          max-height: 80vh;
          overflow-y: auto;
        }

        .shortcuts-content h3 {
          margin-top: 0;
          margin-bottom: 20px;
          font-size: 18px;
          color: #1f2937;
        }

        .shortcuts-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 20px;
          margin-bottom: 20px;
        }

        .shortcut-group h4 {
          margin-top: 0;
          margin-bottom: 12px;
          font-size: 14px;
          color: #374151;
          border-bottom: 1px solid #e5e7eb;
          padding-bottom: 4px;
        }

        .shortcut {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          font-size: 13px;
        }

        .shortcut span {
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
          font-family: monospace;
          font-size: 11px;
          font-weight: 500;
        }

        .close-help {
          background: #3b82f6;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
        }

        .workspace-main {
          display: flex;
          flex: 1;
          overflow: hidden;
        }

        .text-area {
          flex: 1;
          overflow: auto;
          padding: 20px;
        }

        .workspace-status {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 20px;
          background: #f9fafb;
          border-top: 1px solid #e5e7eb;
          font-size: 12px;
          color: #6b7280;
        }

        .selection-info,
        .annotation-info {
          font-style: italic;
        }

        .status-stats {
          display: flex;
          gap: 16px;
        }

        .workspace-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100vh;
        }

        .loading-spinner {
          font-size: 18px;
          color: #6b7280;
        }
      `}</style>
    </div>
  );
};

export default AnnotationWorkspace;
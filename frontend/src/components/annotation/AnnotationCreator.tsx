import React, { useState, useEffect } from 'react';
import { Annotation, Label, SelectionRange } from '../../types/annotation';
import { useAnnotation } from '../../contexts/AnnotationContext';
import LabelSelector from './LabelSelector';

interface AnnotationCreatorProps {
  isOpen: boolean;
  onClose: () => void;
  selection?: SelectionRange | null;
  existingAnnotation?: Annotation;
  labels: Label[];
  onSave: (annotation: Omit<Annotation, 'id' | 'createdAt' | 'updatedAt'>) => void;
  onUpdate?: (id: string, updates: Partial<Annotation>) => void;
  onDelete?: (id: string) => void;
}

const AnnotationCreator: React.FC<AnnotationCreatorProps> = ({
  isOpen,
  onClose,
  selection,
  existingAnnotation,
  labels,
  onSave,
  onUpdate,
  onDelete,
}) => {
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [confidence, setConfidence] = useState<number>(100);
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState<Annotation['status']>('draft');
  
  const isEditing = !!existingAnnotation;

  // Initialize form with existing annotation data or defaults
  useEffect(() => {
    if (existingAnnotation) {
      setSelectedLabels(existingAnnotation.labels);
      setConfidence(existingAnnotation.confidence || 100);
      setNotes(existingAnnotation.notes || '');
      setStatus(existingAnnotation.status);
    } else {
      setSelectedLabels([]);
      setConfidence(100);
      setNotes('');
      setStatus('draft');
    }
  }, [existingAnnotation, isOpen]);

  const handleSave = () => {
    if (selectedLabels.length === 0) {
      alert('Please select at least one label');
      return;
    }

    const annotationData = {
      textId: existingAnnotation?.textId || 'current-document', // TODO: Get from context
      startOffset: existingAnnotation?.startOffset || selection?.startOffset || 0,
      endOffset: existingAnnotation?.endOffset || selection?.endOffset || 0,
      text: existingAnnotation?.text || selection?.text || '',
      labels: selectedLabels,
      confidence: confidence / 100, // Convert percentage to decimal
      notes: notes.trim() || undefined,
      status,
      createdBy: existingAnnotation?.createdBy || 'current-user', // TODO: Get from auth context
    };

    if (isEditing && existingAnnotation) {
      onUpdate?.(existingAnnotation.id, annotationData);
    } else {
      onSave(annotationData);
    }
    
    handleClose();
  };

  const handleDelete = () => {
    if (existingAnnotation && onDelete) {
      if (confirm('Are you sure you want to delete this annotation?')) {
        onDelete(existingAnnotation.id);
        handleClose();
      }
    }
  };

  const handleClose = () => {
    setSelectedLabels([]);
    setConfidence(100);
    setNotes('');
    setStatus('draft');
    onClose();
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      handleClose();
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      handleSave();
    }
  };

  if (!isOpen) return null;

  const selectedText = existingAnnotation?.text || selection?.text || '';

  return (
    <>
      <div className="annotation-creator-overlay" onClick={handleClose} />
      <div className="annotation-creator" onKeyDown={handleKeyDown}>
        <div className="annotation-creator-header">
          <h3>{isEditing ? 'Edit Annotation' : 'Create Annotation'}</h3>
          <button 
            className="close-button"
            onClick={handleClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="annotation-creator-body">
          {/* Selected Text Display */}
          <div className="selected-text-section">
            <label className="section-label">Selected Text:</label>
            <div className="selected-text">
              {selectedText || 'No text selected'}
            </div>
          </div>

          {/* Label Selection */}
          <div className="labels-section">
            <label className="section-label">Labels: *</label>
            <LabelSelector
              labels={labels}
              selectedLabels={selectedLabels}
              onSelectionChange={setSelectedLabels}
              allowMultiple={true}
              showShortcuts={true}
            />
          </div>

          {/* Confidence Score */}
          <div className="confidence-section">
            <label className="section-label">
              Confidence: {confidence}%
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="confidence-slider"
            />
            <div className="confidence-labels">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {/* Status Selection */}
          <div className="status-section">
            <label className="section-label">Status:</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as Annotation['status'])}
              className="status-select"
            >
              <option value="draft">Draft</option>
              <option value="pending">Pending Review</option>
              <option value="validated">Validated</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* Notes */}
          <div className="notes-section">
            <label className="section-label">Notes:</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add optional notes about this annotation..."
              className="notes-textarea"
              rows={3}
            />
          </div>
        </div>

        <div className="annotation-creator-footer">
          <div className="button-group">
            <button 
              className="cancel-button"
              onClick={handleClose}
            >
              Cancel
            </button>
            
            {isEditing && onDelete && (
              <button 
                className="delete-button"
                onClick={handleDelete}
              >
                Delete
              </button>
            )}
            
            <button 
              className="save-button"
              onClick={handleSave}
              disabled={selectedLabels.length === 0}
            >
              {isEditing ? 'Update' : 'Create'} Annotation
            </button>
          </div>

          <div className="shortcuts-info">
            <small>
              Press Ctrl+Enter to save • Esc to cancel
              {labels.some(l => l.shortcut) && ' • Use label shortcuts'}
            </small>
          </div>
        </div>

        <style jsx>{`
          .annotation-creator-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
          }

          .annotation-creator {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            width: 90%;
            max-width: 500px;
            max-height: 90vh;
            overflow: hidden;
            z-index: 1000;
          }

          .annotation-creator-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid #e5e7eb;
          }

          .annotation-creator-header h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
          }

          .close-button {
            background: none;
            border: none;
            font-size: 24px;
            color: #6b7280;
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            transition: background-color 0.2s;
          }

          .close-button:hover {
            background-color: #f3f4f6;
          }

          .annotation-creator-body {
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
          }

          .section-label {
            display: block;
            font-weight: 500;
            color: #374151;
            margin-bottom: 6px;
            font-size: 14px;
          }

          .selected-text-section,
          .labels-section,
          .confidence-section,
          .status-section,
          .notes-section {
            margin-bottom: 20px;
          }

          .selected-text {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 12px;
            font-family: Georgia, serif;
            line-height: 1.5;
            color: #1f2937;
            font-style: italic;
            max-height: 100px;
            overflow-y: auto;
          }

          .confidence-slider {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: #d1d5db;
            outline: none;
            -webkit-appearance: none;
          }

          .confidence-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
          }

          .confidence-slider::-moz-range-thumb {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
            border: none;
          }

          .confidence-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 4px;
            font-size: 12px;
            color: #6b7280;
          }

          .status-select {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            background: white;
            font-size: 14px;
          }

          .status-select:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
          }

          .notes-textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
          }

          .notes-textarea:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
          }

          .annotation-creator-footer {
            padding: 20px;
            border-top: 1px solid #e5e7eb;
            background: #f9fafb;
          }

          .button-group {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            margin-bottom: 8px;
          }

          .cancel-button,
          .delete-button,
          .save-button {
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid;
          }

          .cancel-button {
            background: white;
            border-color: #d1d5db;
            color: #374151;
          }

          .cancel-button:hover {
            background: #f9fafb;
          }

          .delete-button {
            background: #fef2f2;
            border-color: #fca5a5;
            color: #dc2626;
          }

          .delete-button:hover {
            background: #fee2e2;
          }

          .save-button {
            background: #3b82f6;
            border-color: #3b82f6;
            color: white;
          }

          .save-button:hover:not(:disabled) {
            background: #2563eb;
            border-color: #2563eb;
          }

          .save-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .shortcuts-info {
            text-align: center;
            color: #6b7280;
          }
        `}</style>
      </div>
    </>
  );
};

export default AnnotationCreator;
import React, { useRef, useEffect, useMemo } from 'react';
import { useAnnotation } from '../../contexts/AnnotationContext';
import { useTextSelection } from '../../hooks/useTextSelection';
import { Annotation, Label } from '../../types/annotation';

interface TextDisplayProps {
  text: string;
  annotations: Annotation[];
  labels: Label[];
  onAnnotationClick?: (annotation: Annotation) => void;
  onSelectionChange?: (hasSelection: boolean) => void;
}

interface AnnotationSpan {
  start: number;
  end: number;
  annotation: Annotation;
  labels: Label[];
}

const TextDisplay: React.FC<TextDisplayProps> = ({
  text,
  annotations,
  labels,
  onAnnotationClick,
  onSelectionChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { setContainer, selection, clearSelection, selectRange } = useTextSelection();
  const { 
    setCurrentSelection, 
    selectedAnnotationId, 
    setSelectedAnnotationId,
    setShowAnnotationCreator 
  } = useAnnotation();

  // Set up the text selection container
  useEffect(() => {
    setContainer(containerRef.current);
  }, [setContainer]);

  // Handle selection changes
  useEffect(() => {
    setCurrentSelection(selection);
    onSelectionChange?.(!!selection);
  }, [selection, setCurrentSelection, onSelectionChange]);

  // Create annotation spans with overlap handling
  const annotationSpans = useMemo(() => {
    const spans: AnnotationSpan[] = annotations.map(annotation => ({
      start: annotation.startOffset,
      end: annotation.endOffset,
      annotation,
      labels: labels.filter(label => annotation.labels.includes(label.id)),
    }));

    // Sort by start position, then by length (longer spans first for better nesting)
    return spans.sort((a, b) => {
      if (a.start !== b.start) return a.start - b.start;
      return (b.end - b.start) - (a.end - a.start);
    });
  }, [annotations, labels]);

  // Render text with annotations
  const renderAnnotatedText = useMemo(() => {
    if (annotationSpans.length === 0) {
      return <span>{text}</span>;
    }

    const elements: JSX.Element[] = [];
    let lastPosition = 0;

    // Create a map of positions to annotation changes
    const positionMap = new Map<number, { starts: AnnotationSpan[], ends: AnnotationSpan[] }>();
    
    annotationSpans.forEach(span => {
      // Record start positions
      if (!positionMap.has(span.start)) {
        positionMap.set(span.start, { starts: [], ends: [] });
      }
      positionMap.get(span.start)!.starts.push(span);
      
      // Record end positions
      if (!positionMap.has(span.end)) {
        positionMap.set(span.end, { starts: [], ends: [] });
      }
      positionMap.get(span.end)!.ends.push(span);
    });

    const sortedPositions = Array.from(positionMap.keys()).sort((a, b) => a - b);
    const activeSpans: AnnotationSpan[] = [];

    sortedPositions.forEach(position => {
      // Add any plain text before this position
      if (position > lastPosition) {
        const plainText = text.slice(lastPosition, position);
        if (plainText) {
          if (activeSpans.length > 0) {
            // We're inside annotations, wrap with current styling
            const topSpan = activeSpans[activeSpans.length - 1];
            const isSelected = selectedAnnotationId === topSpan.annotation.id;
            const primaryLabel = topSpan.labels[0];
            
            elements.push(
              <span
                key={`text-${lastPosition}-${position}`}
                className={`annotation-highlight ${isSelected ? 'selected' : ''}`}
                style={{ 
                  backgroundColor: primaryLabel?.color + '20',
                  borderColor: primaryLabel?.color,
                }}
              >
                {plainText}
              </span>
            );
          } else {
            elements.push(<span key={`text-${lastPosition}-${position}`}>{plainText}</span>);
          }
        }
      }

      const changes = positionMap.get(position)!;
      
      // Process endings first (in reverse order)
      changes.ends.reverse().forEach(endingSpan => {
        const index = activeSpans.findIndex(span => span === endingSpan);
        if (index !== -1) {
          activeSpans.splice(index, 1);
        }
      });
      
      // Process beginnings
      changes.starts.forEach(startingSpan => {
        activeSpans.push(startingSpan);
      });

      lastPosition = position;
    });

    // Add any remaining text
    if (lastPosition < text.length) {
      const remainingText = text.slice(lastPosition);
      if (activeSpans.length > 0) {
        const topSpan = activeSpans[activeSpans.length - 1];
        const isSelected = selectedAnnotationId === topSpan.annotation.id;
        const primaryLabel = topSpan.labels[0];
        
        elements.push(
          <span
            key={`text-${lastPosition}-end`}
            className={`annotation-highlight ${isSelected ? 'selected' : ''}`}
            style={{ 
              backgroundColor: primaryLabel?.color + '20',
              borderColor: primaryLabel?.color,
            }}
          >
            {remainingText}
          </span>
        );
      } else {
        elements.push(<span key={`text-${lastPosition}-end`}>{remainingText}</span>);
      }
    }

    return <>{elements}</>;
  }, [text, annotationSpans, selectedAnnotationId]);

  const handleClick = (event: React.MouseEvent) => {
    // Find which annotation was clicked
    const target = event.target as HTMLElement;
    if (target.classList.contains('annotation-highlight')) {
      // Find the annotation at this position
      const rect = target.getBoundingClientRect();
      const clickPosition = event.clientX - rect.left;
      
      // For now, we'll use a simpler approach - find annotations that contain the click position
      // This would need more sophisticated logic for overlapping annotations
      const clickedAnnotations = annotationSpans.filter(span => {
        // This is a simplified check - in practice, you'd need to calculate the actual click position
        return true; // For now, just handle the first annotation
      });
      
      if (clickedAnnotations.length > 0) {
        const annotation = clickedAnnotations[0].annotation;
        setSelectedAnnotationId(annotation.id);
        onAnnotationClick?.(annotation);
        
        // Select the annotation text
        selectRange(annotation.startOffset, annotation.endOffset);
      }
    } else {
      // Click on plain text - clear selection
      setSelectedAnnotationId(null);
    }
  };

  const handleDoubleClick = () => {
    // Double-click to create annotation from selection
    if (selection) {
      setShowAnnotationCreator(true);
    }
  };

  return (
    <div className="text-display-container">
      <div
        ref={containerRef}
        className="text-display"
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        style={{
          lineHeight: '1.6',
          fontSize: '16px',
          fontFamily: 'Georgia, serif',
          padding: '20px',
          backgroundColor: '#ffffff',
          border: '1px solid #e5e5e5',
          borderRadius: '8px',
          cursor: 'text',
          userSelect: 'text',
          whiteSpace: 'pre-wrap',
          wordWrap: 'break-word',
        }}
      >
        {renderAnnotatedText}
      </div>
      
      <style jsx>{`
        .annotation-highlight {
          border: 1px solid transparent;
          border-radius: 2px;
          padding: 1px 2px;
          margin: 0 1px;
          cursor: pointer;
          transition: all 0.2s ease;
          position: relative;
        }
        
        .annotation-highlight:hover {
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          transform: translateY(-1px);
        }
        
        .annotation-highlight.selected {
          border-style: solid;
          border-width: 2px;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
        }
        
        .text-display {
          position: relative;
        }
        
        .text-display-container {
          position: relative;
        }
        
        /* Selection styling */
        .text-display::selection {
          background-color: #3B82F6;
          color: white;
        }
        
        .text-display::-moz-selection {
          background-color: #3B82F6;
          color: white;
        }
      `}</style>
    </div>
  );
};

export default TextDisplay;
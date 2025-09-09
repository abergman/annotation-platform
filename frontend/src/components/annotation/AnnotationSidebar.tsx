import React, { useState, useMemo } from 'react';
import { Annotation, Label, AnnotationFilter } from '../../types/annotation';
import { useAnnotation } from '../../contexts/AnnotationContext';

interface AnnotationSidebarProps {
  annotations: Annotation[];
  labels: Label[];
  onAnnotationClick: (annotation: Annotation) => void;
  onAnnotationEdit: (annotation: Annotation) => void;
  onAnnotationDelete: (id: string) => void;
  selectedAnnotationId?: string | null;
}

const AnnotationSidebar: React.FC<AnnotationSidebarProps> = ({
  annotations,
  labels,
  onAnnotationClick,
  onAnnotationEdit,
  onAnnotationDelete,
  selectedAnnotationId,
}) => {
  const { filter, setFilter, filteredAnnotations } = useAnnotation();
  const [sortBy, setSortBy] = useState<'created' | 'updated' | 'confidence' | 'text'>('created');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showFilters, setShowFilters] = useState(false);

  // Sort annotations
  const sortedAnnotations = useMemo(() => {
    const sorted = [...filteredAnnotations].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'created':
          comparison = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          break;
        case 'updated':
          comparison = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
          break;
        case 'confidence':
          comparison = (a.confidence || 0) - (b.confidence || 0);
          break;
        case 'text':
          comparison = a.text.localeCompare(b.text);
          break;
      }
      
      return sortOrder === 'asc' ? comparison : -comparison;
    });
    
    return sorted;
  }, [filteredAnnotations, sortBy, sortOrder]);

  // Group annotations by status
  const groupedAnnotations = useMemo(() => {
    const groups = {
      draft: sortedAnnotations.filter(ann => ann.status === 'draft'),
      pending: sortedAnnotations.filter(ann => ann.status === 'pending'),
      validated: sortedAnnotations.filter(ann => ann.status === 'validated'),
      rejected: sortedAnnotations.filter(ann => ann.status === 'rejected'),
    };
    return groups;
  }, [sortedAnnotations]);

  const handleFilterChange = (newFilter: Partial<AnnotationFilter>) => {
    setFilter(prev => ({ ...prev, ...newFilter }));
  };

  const clearFilters = () => {
    setFilter({});
  };

  const getAnnotationLabels = (annotation: Annotation) => {
    return labels.filter(label => annotation.labels.includes(label.id));
  };

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(date));
  };

  const truncateText = (text: string, maxLength: number = 80) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const getStatusColor = (status: Annotation['status']) => {
    const colors = {
      draft: '#6B7280',
      pending: '#F59E0B',
      validated: '#10B981',
      rejected: '#EF4444',
    };
    return colors[status];
  };

  const AnnotationItem: React.FC<{ annotation: Annotation }> = ({ annotation }) => {
    const annotationLabels = getAnnotationLabels(annotation);
    const isSelected = selectedAnnotationId === annotation.id;

    return (
      <div
        className={`annotation-item ${isSelected ? 'selected' : ''}`}
        onClick={() => onAnnotationClick(annotation)}
      >
        <div className="annotation-header">
          <div className="annotation-labels">
            {annotationLabels.map(label => (
              <span
                key={label.id}
                className="annotation-label"
                style={{ backgroundColor: label.color }}
              >
                {label.name}
              </span>
            ))}
          </div>
          
          <div className="annotation-actions">
            <button
              className="action-button edit"
              onClick={(e) => {
                e.stopPropagation();
                onAnnotationEdit(annotation);
              }}
              title="Edit annotation"
            >
              ✏️
            </button>
            <button
              className="action-button delete"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm('Delete this annotation?')) {
                  onAnnotationDelete(annotation.id);
                }
              }}
              title="Delete annotation"
            >
              🗑️
            </button>
          </div>
        </div>

        <div className="annotation-text">
          {truncateText(annotation.text)}
        </div>

        <div className="annotation-meta">
          <span className="annotation-status">
            <span
              className="status-indicator"
              style={{ backgroundColor: getStatusColor(annotation.status) }}
            />
            {annotation.status}
          </span>
          
          {annotation.confidence !== undefined && (
            <span className="annotation-confidence">
              {Math.round(annotation.confidence * 100)}%
            </span>
          )}
          
          <span className="annotation-date">
            {formatDate(annotation.updatedAt)}
          </span>
        </div>

        {annotation.notes && (
          <div className="annotation-notes">
            {truncateText(annotation.notes, 60)}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="annotation-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h3>Annotations ({annotations.length})</h3>
        <button
          className="filter-toggle"
          onClick={() => setShowFilters(!showFilters)}
          title="Toggle filters"
        >
          🔍
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="filters-section">
          <div className="filter-group">
            <label>Labels:</label>
            <div className="label-filters">
              {labels.map(label => (
                <label key={label.id} className="label-filter">
                  <input
                    type="checkbox"
                    checked={filter.labels?.includes(label.id) || false}
                    onChange={(e) => {
                      const newLabels = filter.labels || [];
                      if (e.target.checked) {
                        handleFilterChange({ labels: [...newLabels, label.id] });
                      } else {
                        handleFilterChange({ labels: newLabels.filter(id => id !== label.id) });
                      }
                    }}
                  />
                  <span style={{ color: label.color }}>{label.name}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <label>Status:</label>
            <div className="status-filters">
              {['draft', 'pending', 'validated', 'rejected'].map(status => (
                <label key={status} className="status-filter">
                  <input
                    type="checkbox"
                    checked={filter.status?.includes(status as Annotation['status']) || false}
                    onChange={(e) => {
                      const newStatuses = filter.status || [];
                      if (e.target.checked) {
                        handleFilterChange({ status: [...newStatuses, status as Annotation['status']] });
                      } else {
                        handleFilterChange({ status: newStatuses.filter(s => s !== status) });
                      }
                    }}
                  />
                  {status}
                </label>
              ))}
            </div>
          </div>

          <button className="clear-filters" onClick={clearFilters}>
            Clear Filters
          </button>
        </div>
      )}

      {/* Sort Controls */}
      <div className="sort-controls">
        <select
          value={`${sortBy}-${sortOrder}`}
          onChange={(e) => {
            const [newSortBy, newSortOrder] = e.target.value.split('-');
            setSortBy(newSortBy as typeof sortBy);
            setSortOrder(newSortOrder as typeof sortOrder);
          }}
        >
          <option value="created-desc">Newest First</option>
          <option value="created-asc">Oldest First</option>
          <option value="updated-desc">Recently Updated</option>
          <option value="confidence-desc">Highest Confidence</option>
          <option value="confidence-asc">Lowest Confidence</option>
          <option value="text-asc">Text A-Z</option>
          <option value="text-desc">Text Z-A</option>
        </select>
      </div>

      {/* Annotation Groups */}
      <div className="annotations-list">
        {Object.entries(groupedAnnotations).map(([status, statusAnnotations]) => {
          if (statusAnnotations.length === 0) return null;
          
          return (
            <div key={status} className="annotation-group">
              <div className="group-header">
                <span className="group-title">
                  {status.charAt(0).toUpperCase() + status.slice(1)} ({statusAnnotations.length})
                </span>
                <span
                  className="group-indicator"
                  style={{ backgroundColor: getStatusColor(status as Annotation['status']) }}
                />
              </div>
              
              <div className="group-items">
                {statusAnnotations.map(annotation => (
                  <AnnotationItem key={annotation.id} annotation={annotation} />
                ))}
              </div>
            </div>
          );
        })}

        {sortedAnnotations.length === 0 && (
          <div className="no-annotations">
            {annotations.length === 0 ? 'No annotations yet' : 'No annotations match filters'}
          </div>
        )}
      </div>

      <style jsx>{`
        .annotation-sidebar {
          width: 350px;
          height: 100%;
          background: #f9fafb;
          border-left: 1px solid #e5e7eb;
          display: flex;
          flex-direction: column;
        }

        .sidebar-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px;
          border-bottom: 1px solid #e5e7eb;
          background: white;
        }

        .sidebar-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: #1f2937;
        }

        .filter-toggle {
          background: none;
          border: none;
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          font-size: 16px;
        }

        .filter-toggle:hover {
          background-color: #f3f4f6;
        }

        .filters-section {
          padding: 12px;
          background: white;
          border-bottom: 1px solid #e5e7eb;
        }

        .filter-group {
          margin-bottom: 12px;
        }

        .filter-group label {
          font-size: 12px;
          font-weight: 500;
          color: #374151;
          margin-bottom: 6px;
          display: block;
        }

        .label-filters,
        .status-filters {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .label-filter,
        .status-filter {
          display: flex;
          align-items: center;
          font-size: 12px;
          cursor: pointer;
          margin: 0;
        }

        .label-filter input,
        .status-filter input {
          margin-right: 4px;
        }

        .clear-filters {
          background: #ef4444;
          color: white;
          border: none;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          cursor: pointer;
        }

        .sort-controls {
          padding: 12px;
          background: white;
          border-bottom: 1px solid #e5e7eb;
        }

        .sort-controls select {
          width: 100%;
          padding: 6px 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 12px;
        }

        .annotations-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px 0;
        }

        .annotation-group {
          margin-bottom: 16px;
        }

        .group-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 16px;
          background: #f3f4f6;
          font-size: 12px;
          font-weight: 600;
          color: #374151;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .group-indicator {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        .annotation-item {
          padding: 12px 16px;
          background: white;
          border-bottom: 1px solid #f3f4f6;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .annotation-item:hover {
          background-color: #f9fafb;
        }

        .annotation-item.selected {
          background-color: #eff6ff;
          border-left: 3px solid #3b82f6;
        }

        .annotation-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 8px;
        }

        .annotation-labels {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }

        .annotation-label {
          padding: 2px 6px;
          border-radius: 10px;
          font-size: 10px;
          font-weight: 500;
          color: white;
        }

        .annotation-actions {
          display: flex;
          gap: 4px;
          opacity: 0;
          transition: opacity 0.2s;
        }

        .annotation-item:hover .annotation-actions {
          opacity: 1;
        }

        .action-button {
          background: none;
          border: none;
          cursor: pointer;
          padding: 2px;
          border-radius: 2px;
          font-size: 12px;
        }

        .action-button:hover {
          background-color: #f3f4f6;
        }

        .annotation-text {
          font-size: 14px;
          color: #1f2937;
          line-height: 1.4;
          margin-bottom: 8px;
        }

        .annotation-meta {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          color: #6b7280;
        }

        .annotation-status {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .status-indicator {
          width: 6px;
          height: 6px;
          border-radius: 50%;
        }

        .annotation-confidence {
          font-weight: 500;
        }

        .annotation-notes {
          margin-top: 8px;
          font-size: 12px;
          color: #6b7280;
          font-style: italic;
        }

        .no-annotations {
          text-align: center;
          color: #6b7280;
          font-style: italic;
          padding: 32px 16px;
        }
      `}</style>
    </div>
  );
};

export default AnnotationSidebar;
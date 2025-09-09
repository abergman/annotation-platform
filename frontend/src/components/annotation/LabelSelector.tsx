import React, { useState, useRef, useEffect } from 'react';
import { Label } from '../../types/annotation';

interface LabelSelectorProps {
  labels: Label[];
  selectedLabels: string[];
  onSelectionChange: (labelIds: string[]) => void;
  allowMultiple?: boolean;
  showShortcuts?: boolean;
  className?: string;
}

const LabelSelector: React.FC<LabelSelectorProps> = ({
  labels,
  selectedLabels,
  onSelectionChange,
  allowMultiple = true,
  showShortcuts = true,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredLabels = labels.filter(label =>
    label.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleLabelToggle = (labelId: string) => {
    if (allowMultiple) {
      const newSelection = selectedLabels.includes(labelId)
        ? selectedLabels.filter(id => id !== labelId)
        : [...selectedLabels, labelId];
      onSelectionChange(newSelection);
    } else {
      onSelectionChange(selectedLabels.includes(labelId) ? [] : [labelId]);
      setIsOpen(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!isOpen && (event.key === 'Enter' || event.key === ' ')) {
      setIsOpen(true);
      setFocusedIndex(-1);
      return;
    }

    if (!isOpen) return;

    switch (event.key) {
      case 'Escape':
        setIsOpen(false);
        setSearchTerm('');
        setFocusedIndex(-1);
        break;
      case 'ArrowDown':
        event.preventDefault();
        setFocusedIndex(prev => 
          prev < filteredLabels.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        event.preventDefault();
        setFocusedIndex(prev => 
          prev > 0 ? prev - 1 : filteredLabels.length - 1
        );
        break;
      case 'Enter':
        event.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < filteredLabels.length) {
          handleLabelToggle(filteredLabels[focusedIndex].id);
        }
        break;
      default:
        // Check for label shortcuts
        if (showShortcuts && !event.ctrlKey && !event.altKey && !event.metaKey) {
          const shortcutLabel = labels.find(label => 
            label.shortcut === event.key.toLowerCase()
          );
          if (shortcutLabel) {
            event.preventDefault();
            handleLabelToggle(shortcutLabel.id);
          }
        }
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchTerm('');
        setFocusedIndex(-1);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const selectedLabelObjects = labels.filter(label => selectedLabels.includes(label.id));

  return (
    <div className={`label-selector ${className}`} ref={dropdownRef}>
      <div 
        className="label-selector-trigger"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        {selectedLabelObjects.length > 0 ? (
          <div className="selected-labels">
            {selectedLabelObjects.map(label => (
              <span
                key={label.id}
                className="selected-label"
                style={{ backgroundColor: label.color, color: 'white' }}
              >
                {label.name}
                {allowMultiple && (
                  <button
                    className="remove-label"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleLabelToggle(label.id);
                    }}
                    aria-label={`Remove ${label.name} label`}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
          </div>
        ) : (
          <span className="placeholder">Select labels...</span>
        )}
        
        <div className="dropdown-arrow">
          {isOpen ? '▲' : '▼'}
        </div>
      </div>

      {isOpen && (
        <div className="label-dropdown">
          <div className="search-container">
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setFocusedIndex(-1);
              }}
              placeholder="Search labels..."
              className="label-search"
            />
          </div>
          
          <div className="label-list" role="listbox">
            {filteredLabels.length === 0 ? (
              <div className="no-labels">No labels found</div>
            ) : (
              filteredLabels.map((label, index) => (
                <div
                  key={label.id}
                  className={`label-option ${
                    selectedLabels.includes(label.id) ? 'selected' : ''
                  } ${index === focusedIndex ? 'focused' : ''}`}
                  onClick={() => handleLabelToggle(label.id)}
                  role="option"
                  aria-selected={selectedLabels.includes(label.id)}
                >
                  <div className="label-info">
                    <span
                      className="label-color"
                      style={{ backgroundColor: label.color }}
                    />
                    <span className="label-name">{label.name}</span>
                    {showShortcuts && label.shortcut && (
                      <span className="label-shortcut">({label.shortcut})</span>
                    )}
                  </div>
                  
                  {label.description && (
                    <div className="label-description">{label.description}</div>
                  )}
                  
                  <div className="label-checkbox">
                    {selectedLabels.includes(label.id) ? '✓' : ''}
                  </div>
                </div>
              ))
            )}
          </div>
          
          {showShortcuts && (
            <div className="shortcuts-hint">
              Press label shortcut keys or use ↑↓ arrows and Enter
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .label-selector {
          position: relative;
          width: 100%;
        }

        .label-selector-trigger {
          display: flex;
          align-items: center;
          min-height: 40px;
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          background: white;
          cursor: pointer;
          transition: border-color 0.2s;
        }

        .label-selector-trigger:hover {
          border-color: #9ca3af;
        }

        .label-selector-trigger:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }

        .selected-labels {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          flex: 1;
        }

        .selected-label {
          display: flex;
          align-items: center;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }

        .remove-label {
          background: none;
          border: none;
          color: inherit;
          margin-left: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
        }

        .remove-label:hover {
          opacity: 0.7;
        }

        .placeholder {
          color: #9ca3af;
          flex: 1;
        }

        .dropdown-arrow {
          margin-left: 8px;
          color: #6b7280;
          font-size: 12px;
        }

        .label-dropdown {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          z-index: 1000;
          background: white;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
          max-height: 300px;
          overflow: hidden;
        }

        .search-container {
          padding: 8px;
          border-bottom: 1px solid #e5e7eb;
        }

        .label-search {
          width: 100%;
          padding: 6px 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 14px;
        }

        .label-search:focus {
          outline: none;
          border-color: #3b82f6;
        }

        .label-list {
          max-height: 200px;
          overflow-y: auto;
        }

        .label-option {
          display: flex;
          align-items: center;
          padding: 8px 12px;
          cursor: pointer;
          border-bottom: 1px solid #f3f4f6;
        }

        .label-option:hover,
        .label-option.focused {
          background-color: #f9fafb;
        }

        .label-option.selected {
          background-color: #eff6ff;
        }

        .label-info {
          display: flex;
          align-items: center;
          flex: 1;
        }

        .label-color {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          margin-right: 8px;
        }

        .label-name {
          font-weight: 500;
          margin-right: 8px;
        }

        .label-shortcut {
          color: #6b7280;
          font-size: 12px;
        }

        .label-description {
          color: #6b7280;
          font-size: 12px;
          margin-top: 2px;
          margin-left: 20px;
        }

        .label-checkbox {
          color: #22c55e;
          font-weight: bold;
        }

        .no-labels {
          padding: 12px;
          text-align: center;
          color: #6b7280;
        }

        .shortcuts-hint {
          padding: 6px 12px;
          background-color: #f9fafb;
          color: #6b7280;
          font-size: 11px;
          border-top: 1px solid #e5e7eb;
        }
      `}</style>
    </div>
  );
};

export default LabelSelector;
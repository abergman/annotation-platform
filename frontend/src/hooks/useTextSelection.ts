import { useState, useCallback, useRef, useEffect } from 'react';
import { SelectionRange } from '../types/annotation';

export const useTextSelection = () => {
  const [selection, setSelection] = useState<SelectionRange | null>(null);
  const containerRef = useRef<HTMLElement | null>(null);
  const selectionTimeoutRef = useRef<NodeJS.Timeout>();

  const getTextOffsetInContainer = useCallback((container: HTMLElement, node: Node, offset: number): number => {
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      null
    );

    let totalOffset = 0;
    let currentNode;
    
    while (currentNode = walker.nextNode()) {
      if (currentNode === node) {
        return totalOffset + offset;
      }
      totalOffset += currentNode.textContent?.length || 0;
    }
    
    return totalOffset;
  }, []);

  const getSelectionText = useCallback((): string => {
    const selection = window.getSelection();
    return selection ? selection.toString() : '';
  }, []);

  const handleSelectionChange = useCallback(() => {
    // Clear any existing timeout
    if (selectionTimeoutRef.current) {
      clearTimeout(selectionTimeoutRef.current);
    }

    // Debounce selection changes to avoid excessive updates
    selectionTimeoutRef.current = setTimeout(() => {
      const windowSelection = window.getSelection();
      
      if (!windowSelection || windowSelection.rangeCount === 0 || !containerRef.current) {
        setSelection(null);
        return;
      }

      const range = windowSelection.getRangeAt(0);
      const selectedText = windowSelection.toString().trim();

      // Only process selections within our container
      if (!containerRef.current.contains(range.commonAncestorContainer)) {
        setSelection(null);
        return;
      }

      // Ignore empty selections
      if (!selectedText) {
        setSelection(null);
        return;
      }

      try {
        const startOffset = getTextOffsetInContainer(
          containerRef.current,
          range.startContainer,
          range.startOffset
        );
        
        const endOffset = getTextOffsetInContainer(
          containerRef.current,
          range.endContainer,
          range.endOffset
        );

        const selectionRange: SelectionRange = {
          startContainer: range.startContainer,
          endContainer: range.endContainer,
          startOffset,
          endOffset,
          text: selectedText,
        };

        setSelection(selectionRange);
      } catch (error) {
        console.warn('Error calculating text selection offsets:', error);
        setSelection(null);
      }
    }, 100);
  }, [getTextOffsetInContainer]);

  const clearSelection = useCallback(() => {
    const windowSelection = window.getSelection();
    if (windowSelection) {
      windowSelection.removeAllRanges();
    }
    setSelection(null);
  }, []);

  const selectRange = useCallback((startOffset: number, endOffset: number) => {
    if (!containerRef.current) return;

    const walker = document.createTreeWalker(
      containerRef.current,
      NodeFilter.SHOW_TEXT,
      null
    );

    let currentOffset = 0;
    let startNode: Text | null = null;
    let endNode: Text | null = null;
    let startNodeOffset = 0;
    let endNodeOffset = 0;
    let currentNode;

    while (currentNode = walker.nextNode()) {
      const textNode = currentNode as Text;
      const nodeLength = textNode.textContent?.length || 0;
      
      // Find start node
      if (!startNode && currentOffset + nodeLength >= startOffset) {
        startNode = textNode;
        startNodeOffset = startOffset - currentOffset;
      }
      
      // Find end node
      if (!endNode && currentOffset + nodeLength >= endOffset) {
        endNode = textNode;
        endNodeOffset = endOffset - currentOffset;
        break;
      }
      
      currentOffset += nodeLength;
    }

    if (startNode && endNode) {
      const range = document.createRange();
      range.setStart(startNode, startNodeOffset);
      range.setEnd(endNode, endNodeOffset);

      const windowSelection = window.getSelection();
      if (windowSelection) {
        windowSelection.removeAllRanges();
        windowSelection.addRange(range);
      }
    }
  }, []);

  const setContainer = useCallback((element: HTMLElement | null) => {
    containerRef.current = element;
  }, []);

  // Set up event listeners
  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current);
      }
    };
  }, [handleSelectionChange]);

  return {
    selection,
    setContainer,
    clearSelection,
    selectRange,
    getSelectionText,
  };
};
import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * Encapsulates open/close state and outside-click / Escape-key behaviour
 * for dropdown menus. Both event listeners are only attached while the
 * dropdown is open, avoiding unnecessary work when it is closed.
 */
export function useDropdown() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  const toggle = useCallback(() => setOpen((prev) => !prev), []);

  return { open, setOpen, toggle, containerRef };
}

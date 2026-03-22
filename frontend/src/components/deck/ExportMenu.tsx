import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { exportDeck } from '../../api/decks';
import type { DeckExportFormat } from '../../api/types';

interface ExportMenuProps {
  deckId: number;
}

const FORMATS: { value: DeckExportFormat; label: string; description: string }[] = [
  { value: 'csv', label: 'CSV', description: 'Spreadsheet-compatible format' },
  { value: 'moxfield', label: 'Moxfield', description: 'Import to Moxfield.com' },
  { value: 'archidekt', label: 'Archidekt', description: 'Import to Archidekt.com' },
];

/**
 * Dropdown export button that fetches deck content and triggers a file download.
 *
 * Usage:
 *   <ExportMenu deckId={42} />
 */
export default function ExportMenu({ deckId }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const mutation = useMutation({
    mutationFn: (format: DeckExportFormat) => exportDeck(deckId, format),
    onSuccess: (data) => {
      // Determine MIME type
      const mimeMap: Record<DeckExportFormat, string> = {
        csv: 'text/csv',
        moxfield: 'text/plain',
        archidekt: 'text/plain',
      };
      const mime = mimeMap[data.format] ?? 'text/plain';
      const ext = data.format === 'csv' ? 'csv' : 'txt';

      // Trigger browser download
      const blob = new Blob([data.content], { type: mime });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `deck-${data.deck_id}-${data.format}.${ext}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);

      setOpen(false);
    },
  });

  const handleExport = (format: DeckExportFormat) => {
    if (!mutation.isPending) {
      mutation.mutate(format);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={mutation.isPending}
        className={[
          'flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium',
          'text-[var(--color-text-primary)] bg-[var(--color-surface-alt)]',
          'hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
          'disabled:opacity-50 disabled:cursor-not-allowed',
        ].join(' ')}
      >
        <svg
          className="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        {mutation.isPending ? 'Exporting...' : 'Export'}
        <svg
          className={['h-3 w-3 transition-transform', open ? 'rotate-180' : ''].join(' ')}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Export format options"
          className={[
            'absolute right-0 z-50 mt-1 w-52 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-surface-alt)] shadow-2xl',
          ].join(' ')}
        >
          {FORMATS.map(({ value, label, description }) => (
            <button
              key={value}
              type="button"
              role="menuitem"
              onClick={() => handleExport(value)}
              className={[
                'flex w-full flex-col items-start px-4 py-3 text-left transition-colors',
                'hover:bg-[var(--color-surface-raised)]',
                'focus:outline-none focus:bg-[var(--color-surface-raised)]',
                'first:rounded-t-lg last:rounded-b-lg',
              ].join(' ')}
            >
              <span className="text-sm font-medium text-[var(--color-text-primary)]">{label}</span>
              <span className="text-xs text-[var(--color-text-secondary)]">{description}</span>
            </button>
          ))}
        </div>
      )}

      {mutation.isError && (
        <p className="absolute right-0 top-full mt-1 text-xs text-[var(--color-budget-over)]">
          Export failed. Try again.
        </p>
      )}
    </div>
  );
}

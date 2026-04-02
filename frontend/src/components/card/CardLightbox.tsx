import { useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import CardImage from './CardImage';

interface CardLightboxProps {
  imageUrl: string;
  cardName: string;
  onClose: () => void;
}

export default function CardLightbox({ imageUrl, cardName, onClose }: CardLightboxProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Card image: ${cardName}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] max-w-[min(90vw,480px)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close lightbox"
          className="absolute -right-2 -top-2 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-surface)] text-[var(--color-text-secondary)] shadow-lg hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        {/* Card image */}
        <CardImage imageUrl={imageUrl} name={cardName} size="large" />

        {/* Card name */}
        <p className="mt-2 text-center text-sm font-medium text-white">{cardName}</p>
      </div>
    </div>,
    document.body,
  );
}

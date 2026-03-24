import { useState, useRef, useEffect } from 'react';
import type { DeckCardResponse } from '../../api/types';
import { getCardMarketplaceOptions } from '../../utils/marketplace';

interface MarketplaceLinksProps {
  card: DeckCardResponse;
}

/**
 * Per-card buy dropdown showing marketplace links with prices.
 * Cheapest option is highlighted. Opens links in a new tab.
 */
export default function MarketplaceLinks({ card }: MarketplaceLinksProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const options = getCardMarketplaceOptions(card);
  const cheapest = options
    .filter((o) => o.price != null)
    .sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity))[0]?.marketplace;

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

  return (
    <div
      ref={containerRef}
      className="relative"
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Buy ${card.card_name}`}
        title="Buy this card"
        className={[
          'flex items-center justify-center rounded p-1 text-[var(--color-text-secondary)]',
          'hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
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
          <circle cx="9" cy="21" r="1" />
          <circle cx="20" cy="21" r="1" />
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Marketplace options"
          className={[
            'absolute right-0 z-50 mt-1 w-48 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-surface-alt)] shadow-2xl',
          ].join(' ')}
        >
          {options.map(({ marketplace, label, price, url }) => {
            const isCheapest = marketplace === cheapest;

            if (!url) return null;

            return (
              <a
                key={marketplace}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                role="menuitem"
                onClick={() => setOpen(false)}
                className={[
                  'flex w-full items-center justify-between px-3 py-2 text-left transition-colors',
                  'hover:bg-[var(--color-surface-raised)]',
                  'focus:outline-none focus:bg-[var(--color-surface-raised)]',
                  'first:rounded-t-lg last:rounded-b-lg',
                ].join(' ')}
              >
                <span className="flex items-center gap-1.5">
                  <span className="text-sm text-[var(--color-text-primary)]">{label}</span>
                  {isCheapest && (
                    <span className="rounded bg-green-900 px-1 py-0.5 text-[10px] font-bold uppercase text-green-300">
                      Best
                    </span>
                  )}
                </span>
                {price != null && (
                  <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                    ${price.toFixed(2)}
                  </span>
                )}
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

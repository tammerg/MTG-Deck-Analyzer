import { useState, useRef, useEffect } from 'react';
import type { DeckCardResponse } from '../../api/types';
import {
  getDeckPurchaseUrl,
  getDeckTotalForMarketplace,
  recommendMarketplace,
  MARKETPLACE_LABELS,
  type Marketplace,
} from '../../utils/marketplace';

interface BuyAllMenuProps {
  cards: DeckCardResponse[];
}

const MARKETPLACES: Marketplace[] = ['tcgplayer', 'cardkingdom'];

/**
 * Deck-level "Buy All" dropdown showing marketplace links with total prices.
 * Cheapest marketplace gets a "BEST PRICE" badge.
 */
export default function BuyAllMenu({ cards }: BuyAllMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const recommended = recommendMarketplace(cards);

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
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={[
          'flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium',
          'text-[var(--color-text-primary)] bg-[var(--color-surface-alt)]',
          'hover:bg-[var(--color-surface-raised)] transition-colors',
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
        Buy All
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
          aria-label="Buy deck options"
          className={[
            'absolute right-0 z-50 mt-1 w-60 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-surface-alt)] shadow-2xl',
          ].join(' ')}
        >
          {MARKETPLACES.map((marketplace) => {
            const total = getDeckTotalForMarketplace(marketplace, cards);
            const url = getDeckPurchaseUrl(marketplace, cards);
            const isBest = marketplace === recommended;

            return (
              <a
                key={marketplace}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                role="menuitem"
                onClick={() => setOpen(false)}
                className={[
                  'flex w-full items-center justify-between px-4 py-3 text-left transition-colors',
                  'hover:bg-[var(--color-surface-raised)]',
                  'focus:outline-none focus:bg-[var(--color-surface-raised)]',
                  'first:rounded-t-lg last:rounded-b-lg',
                ].join(' ')}
              >
                <span className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {MARKETPLACE_LABELS[marketplace]}
                  </span>
                  {isBest && (
                    <span className="rounded bg-green-900 px-1.5 py-0.5 text-[10px] font-bold uppercase text-green-300">
                      Best Price
                    </span>
                  )}
                </span>
                <span className="text-sm text-[var(--color-text-secondary)]">
                  {total != null ? `$${total.toFixed(2)}` : 'N/A'}
                </span>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

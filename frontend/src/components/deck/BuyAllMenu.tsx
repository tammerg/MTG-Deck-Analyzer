import type { DeckCardResponse } from '../../api/types';
import {
  getDeckPurchaseUrl,
  getDeckTotalForMarketplace,
  MARKETPLACE_LABELS,
  type Marketplace,
} from '../../utils/marketplace';
import { useDropdown } from '../../hooks/useDropdown';
import { CartIcon } from '../icons/CartIcon';

interface BuyAllMenuProps {
  cards: DeckCardResponse[];
}

const MARKETPLACES: Marketplace[] = ['tcgplayer', 'cardkingdom'];

/**
 * Deck-level "Buy All" dropdown showing marketplace links with total prices.
 *
 * Note: a "Best Price" badge is intentionally absent — both marketplaces
 * currently return the same TCGPlayer-sourced price, making the recommendation
 * from `recommendMarketplace` meaningless. Re-introduce the badge once
 * distinct per-marketplace pricing is available.
 */
export default function BuyAllMenu({ cards }: BuyAllMenuProps) {
  const { open, toggle, setOpen, containerRef } = useDropdown();

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        className={[
          'flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium',
          'text-[var(--color-text-primary)] bg-[var(--color-surface-alt)]',
          'hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
        ].join(' ')}
      >
        <CartIcon className="h-4 w-4" />
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
          aria-label="Buy deck options"
          className={[
            'absolute right-0 z-50 mt-1 w-60 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-surface-alt)] shadow-2xl',
          ].join(' ')}
        >
          {MARKETPLACES.map((marketplace) => {
            const total = getDeckTotalForMarketplace(marketplace, cards);
            const url = getDeckPurchaseUrl(marketplace, cards);

            return (
              <a
                key={marketplace}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpen(false)}
                className={[
                  'flex w-full items-center justify-between px-4 py-3 text-left transition-colors',
                  'hover:bg-[var(--color-surface-raised)]',
                  'focus:outline-none focus:bg-[var(--color-surface-raised)]',
                  'first:rounded-t-lg last:rounded-b-lg',
                ].join(' ')}
              >
                <span className="text-sm font-medium text-[var(--color-text-primary)]">
                  {MARKETPLACE_LABELS[marketplace]}
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

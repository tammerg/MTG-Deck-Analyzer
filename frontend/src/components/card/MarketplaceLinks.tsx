import { useMemo } from 'react';
import type { DeckCardResponse } from '../../api/types';
import { getCardMarketplaceOptions } from '../../utils/marketplace';
import { useDropdown } from '../../hooks/useDropdown';
import { CartIcon } from '../icons/CartIcon';

interface MarketplaceLinksProps {
  card: DeckCardResponse;
}

/**
 * Per-card buy dropdown showing marketplace links with prices.
 * Opens links in a new tab.
 *
 * Note: a "Best" / cheapest badge is intentionally absent — both marketplaces
 * currently return the same TCGPlayer-sourced price, making any highlight
 * misleading. Re-introduce the badge once distinct per-marketplace pricing
 * is available.
 */
export default function MarketplaceLinks({ card }: MarketplaceLinksProps) {
  const { open, toggle, setOpen, containerRef } = useDropdown();

  const options = useMemo(() => getCardMarketplaceOptions(card), [card]);

  return (
    <div
      ref={containerRef}
      className="relative"
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`Buy ${card.card_name}`}
        title="Buy this card"
        className={[
          'flex items-center justify-center rounded p-1 text-[var(--color-text-secondary)]',
          'hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
        ].join(' ')}
      >
        <CartIcon className="h-4 w-4" />
      </button>

      {open && (
        <div
          aria-label="Marketplace options"
          className={[
            'absolute right-0 z-50 mt-1 w-48 rounded-lg border border-[var(--color-border)]',
            'bg-[var(--color-surface-alt)] shadow-2xl',
          ].join(' ')}
        >
          {options.map(({ marketplace, label, price, url }) => {
            if (!url) return null;

            return (
              <a
                key={marketplace}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpen(false)}
                className={[
                  'flex w-full items-center justify-between px-3 py-2 text-left transition-colors',
                  'hover:bg-[var(--color-surface-raised)]',
                  'focus:outline-none focus:bg-[var(--color-surface-raised)]',
                  'first:rounded-t-lg last:rounded-b-lg',
                ].join(' ')}
              >
                <span className="text-sm text-[var(--color-text-primary)]">{label}</span>
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

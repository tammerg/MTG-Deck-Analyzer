import { useState } from 'react';
import type { DeckCardResponse } from '../../api/types';
import CardListItem from '../card/CardListItem';
import { getCategoryDisplayName, getCategoryColor } from '../../utils/categories';

interface DeckCategoryGroupProps {
  category: string;
  cards: DeckCardResponse[];
  budget?: number;
  /** Whether the group starts expanded. Defaults to true. */
  defaultExpanded?: boolean;
}

/**
 * Collapsible card list section grouped by deck category.
 * Cards are sorted by CMC within the group.
 *
 * Usage:
 *   <DeckCategoryGroup
 *     category="ramp"
 *     cards={rampCards}
 *     budget={200}
 *   />
 */
export default function DeckCategoryGroup({
  category,
  cards,
  budget,
  defaultExpanded = true,
}: DeckCategoryGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Sort cards by CMC within category
  const sortedCards = [...cards].sort((a, b) => a.cmc - b.cmc);

  const displayName = getCategoryDisplayName(category);
  const colorClass = getCategoryColor(category);
  const headingId = `category-heading-${category}`;

  return (
    <section aria-labelledby={headingId}>
      {/* Collapsible header */}
      <button
        type="button"
        id={headingId}
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        className={[
          'flex w-full items-center justify-between rounded-md px-3 py-2 text-left',
          'hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
        ].join(' ')}
      >
        <div className="flex items-center gap-2">
          {/* Category badge */}
          <span
            className={[
              'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
              colorClass,
            ].join(' ')}
            aria-hidden="true"
          >
            {displayName}
          </span>

          {/* Card count */}
          <span className="text-sm text-[var(--color-text-secondary)]">
            ({cards.length})
          </span>
        </div>

        {/* Chevron */}
        <svg
          className={[
            'h-4 w-4 text-[var(--color-text-secondary)] transition-transform duration-200',
            expanded ? 'rotate-180' : '',
          ].join(' ')}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Card list */}
      {expanded && (
        <ul className="mt-1 space-y-1 pl-2" role="list">
          {sortedCards.map((card) => (
            <li key={card.card_id}>
              <CardListItem variant="deck-card" card={card} budget={budget} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

import type { CardResponse } from '../../api/types';
import CardImage from './CardImage';
import LoadingCard from './LoadingCard';
import { truncate } from '../../utils/format';
import { extractScryfallId } from '../../utils/scryfall';

interface CardGridProps {
  cards: CardResponse[];
  loading?: boolean;
  loadingCount?: number;
  onCardClick?: (card: CardResponse) => void;
  columns?: 2 | 3 | 4 | 5 | 6;
}

const COLUMN_CLASSES: Record<number, string> = {
  2: 'grid-cols-2',
  3: 'grid-cols-2 sm:grid-cols-3',
  4: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4',
  5: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5',
  6: 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6',
};

/**
 * Responsive grid of card images with optional click handler.
 *
 * Usage:
 *   <CardGrid cards={cards} onCardClick={handleSelect} />
 *   <CardGrid cards={[]} loading loadingCount={12} columns={4} />
 */
export default function CardGrid({
  cards,
  loading = false,
  loadingCount = 6,
  onCardClick,
  columns = 4,
}: CardGridProps) {
  const gridClass = COLUMN_CLASSES[columns] ?? COLUMN_CLASSES[4];

  if (loading) {
    return (
      <div className={`grid ${gridClass} gap-4`} aria-busy="true">
        {Array.from({ length: loadingCount }).map((_, i) => (
          <LoadingCard key={i} />
        ))}
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <p className="py-12 text-center text-[var(--color-text-secondary)]">
        No cards found.
      </p>
    );
  }

  return (
    <div className={`grid ${gridClass} gap-4`}>
      {cards.map((card) => {
        const scryfallId = card.image_url ? extractScryfallId(card.image_url) ?? undefined : undefined;
        return (
          <div
            key={card.id}
            className={[
              'group flex flex-col gap-1',
              onCardClick ? 'cursor-pointer' : '',
            ].join(' ')}
            onClick={() => onCardClick?.(card)}
            onKeyDown={(e) => {
              if ((e.key === 'Enter' || e.key === ' ') && onCardClick) {
                e.preventDefault();
                onCardClick(card);
              }
            }}
            role={onCardClick ? 'button' : undefined}
            tabIndex={onCardClick ? 0 : undefined}
            aria-label={card.name}
          >
            <div
              className={[
                'rounded-lg overflow-hidden transition-transform duration-150',
                onCardClick ? 'group-hover:scale-[1.02] group-focus:scale-[1.02]' : '',
              ].join(' ')}
            >
              <CardImage
                scryfallId={scryfallId}
                imageUrl={card.image_url}
                name={card.name}
                size="normal"
              />
            </div>
            <p
              className="text-center text-xs text-[var(--color-text-secondary)] truncate px-1"
              title={card.name}
            >
              {truncate(card.name, 22)}
            </p>
          </div>
        );
      })}
    </div>
  );
}

import type { CardResponse } from '../../api/types';
import CardListItem from '../card/CardListItem';
import LoadingCard from '../card/LoadingCard';

interface SearchResultsProps {
  results: CardResponse[];
  loading?: boolean;
  error?: Error | null;
  onCardClick?: (card: CardResponse) => void;
  view?: 'list' | 'grid';
}

/**
 * Renders a list or grid of card search results with loading and error states.
 *
 * Usage:
 *   <SearchResults results={cards} loading={isFetching} onCardClick={handleSelect} />
 */
export default function SearchResults({
  results,
  loading = false,
  error = null,
  onCardClick,
}: SearchResultsProps) {
  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-[var(--color-budget-over)] bg-red-950 p-4 text-sm text-[var(--color-budget-over)]"
      >
        Error loading cards: {error.message}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading search results">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="animate-pulse flex items-center gap-3 rounded-md px-3 py-3 bg-[var(--color-surface-alt)] border border-[var(--color-border)]">
            <div className="h-3 w-1/3 rounded bg-[var(--color-surface-raised)]" />
            <div className="h-3 w-1/4 rounded bg-[var(--color-surface-raised)]" />
            <div className="ml-auto h-3 w-12 rounded bg-[var(--color-surface-raised)]" />
          </div>
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="py-16 text-center text-[var(--color-text-secondary)]">
        <p className="text-lg">No cards found.</p>
        <p className="text-sm mt-1">Try adjusting your search or filters.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1" role="list" aria-label="Search results">
      {results.map((card) => (
        <div key={card.id} role="listitem">
          <CardListItem
            variant="card"
            card={card}
            onClick={onCardClick}
          />
        </div>
      ))}
    </div>
  );
}

// Unused import cleanup
void LoadingCard;

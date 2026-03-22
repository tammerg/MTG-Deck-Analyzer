import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import CardSearchFilters, { type SearchFilters } from '../components/search/CardSearchFilters';
import SearchResults from '../components/search/SearchResults';
import { searchCards } from '../api/cards';
import type { CardResponse } from '../api/types';
import { useEffect } from 'react';

const PAGE_SIZE = 20;

/**
 * Full-featured card search page with filters and pagination.
 */
export default function SearchPage() {
  useEffect(() => {
    document.title = 'Search | MTG Deck Maker';
  }, []);

  const [filters, setFilters] = useState<SearchFilters>({
    q: '',
    color_identity: [],
    type: '',
  });
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [page, setPage] = useState(0);
  const [selectedCard, setSelectedCard] = useState<CardResponse | null>(null);

  // 400ms debounce for filters
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilters(filters);
      setPage(0);
    }, 400);
    return () => clearTimeout(timer);
  }, [filters]);

  // Map UI filter names to backend API param names
  const searchParams = {
    q: debouncedFilters.q || undefined,
    color: debouncedFilters.color_identity.join('') || undefined,
    type: debouncedFilters.type || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };

  const hasFilters = Boolean(
    debouncedFilters.q || debouncedFilters.color_identity.length || debouncedFilters.type
  );

  const { data, isFetching, error } = useQuery({
    queryKey: ['cards', 'search', searchParams],
    queryFn: () => searchCards(searchParams),
    enabled: hasFilters,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const results = data?.results ?? [];
  const total = data?.total ?? 0;

  const handleFiltersChange = (next: SearchFilters) => {
    setFilters(next);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Card Search</h1>

      <CardSearchFilters filters={filters} onChange={handleFiltersChange} />

      {/* Result count */}
      {!isFetching && hasFilters && (
        <p className="text-sm text-[var(--color-text-secondary)]">
          {total > 0
            ? `Showing ${page * PAGE_SIZE + 1}--${Math.min(page * PAGE_SIZE + results.length, total)} of ${total} results`
            : `${results.length} result${results.length !== 1 ? 's' : ''}`}
        </p>
      )}

      <SearchResults
        results={results}
        loading={isFetching}
        error={error as Error | null}
        onCardClick={setSelectedCard}
      />

      {/* Pagination */}
      {hasFilters && results.length > 0 && (
        <div className="flex items-center justify-center gap-4 py-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || isFetching}
            className={[
              'rounded-md px-4 py-2 text-sm font-medium transition-colors',
              'border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
              'hover:bg-[var(--color-surface-raised)] disabled:opacity-40 disabled:cursor-not-allowed',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            Previous
          </button>
          <span className="text-sm text-[var(--color-text-secondary)]">
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= totalPages - 1 || isFetching}
            className={[
              'rounded-md px-4 py-2 text-sm font-medium transition-colors',
              'border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
              'hover:bg-[var(--color-surface-raised)] disabled:opacity-40 disabled:cursor-not-allowed',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            Next
          </button>
        </div>
      )}

      {/* Selected card detail panel */}
      {selectedCard && (
        <aside
          aria-label="Selected card detail"
          className="fixed bottom-4 right-4 z-40 w-72 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-alt)] shadow-2xl"
        >
          <div className="flex items-start justify-between p-3">
            <div>
              <h3 className="font-semibold text-[var(--color-text-primary)]">{selectedCard.name}</h3>
              <p className="text-xs text-[var(--color-text-secondary)]">{selectedCard.type_line}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedCard(null)}
              aria-label="Close card detail"
              className="ml-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            >
              &times;
            </button>
          </div>
          {selectedCard.oracle_text && (
            <p className="px-3 pb-3 text-xs text-[var(--color-text-secondary)] leading-relaxed">
              {selectedCard.oracle_text}
            </p>
          )}
        </aside>
      )}
    </div>
  );
}

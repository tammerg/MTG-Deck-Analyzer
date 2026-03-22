import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchCards } from '../api/cards';
import type { CardSearchParams } from '../api/types';

interface UseCardSearchOptions {
  debounceMs?: number;
  enabled?: boolean;
}

/**
 * TanStack Query wrapper for card search with built-in debouncing.
 *
 * Usage:
 *   const { cards, isLoading, error, setFilters } = useCardSearch({ debounceMs: 400 });
 *
 *   // Trigger a search
 *   setFilters({ q: 'Atraxa', color: 'WUBG', limit: 20 });
 */
export function useCardSearch(options: UseCardSearchOptions = {}) {
  const { debounceMs = 300, enabled = true } = options;

  const [filters, setFilters] = useState<CardSearchParams>({});
  const [debouncedFilters, setDebouncedFilters] = useState<CardSearchParams>({});

  // Debounce filter changes
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilters(filters);
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [filters, debounceMs]);

  const hasQuery = Boolean(
    debouncedFilters.q ||
      debouncedFilters.color ||
      debouncedFilters.type
  );

  const query = useQuery({
    queryKey: ['cards', 'search', debouncedFilters],
    queryFn: () => searchCards(debouncedFilters),
    enabled: enabled && hasQuery,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  return {
    cards: query.data?.results ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isFetching,
    error: query.error as Error | null,
    setFilters,
    filters,
    refetch: query.refetch,
  };
}

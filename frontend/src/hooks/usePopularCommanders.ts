import { useQuery } from '@tanstack/react-query';
import { getPopularCommanders } from '../api/cards';

/**
 * TanStack Query hook for fetching popular commanders from EDHREC.
 *
 * Usage:
 *   const { commanders, isLoading, error } = usePopularCommanders(20);
 */
export function usePopularCommanders(limit = 20) {
  const query = useQuery({
    queryKey: ['commanders', 'popular', limit],
    queryFn: () => getPopularCommanders(limit),
    staleTime: 60 * 60 * 1000, // 1 hour
  });

  return {
    commanders: query.data?.commanders ?? [],
    isLoading: query.isLoading,
    error: query.error as Error | null,
  };
}

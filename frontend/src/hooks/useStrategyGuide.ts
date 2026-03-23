import { useMutation } from '@tanstack/react-query';
import { getStrategyGuide } from '../api/decks';
import type { StrategyGuideRequest, StrategyGuideResponse } from '../api/types';

/**
 * Hook for on-demand strategy guide generation.
 *
 * Uses useMutation (not useQuery) since generation is triggered by button click.
 *
 * Usage:
 *   const { generate, data, isPending, error } = useStrategyGuide(deckId);
 *   <button onClick={() => generate()}>Generate</button>
 */
export function useStrategyGuide(deckId: number) {
  const { mutate, data, isPending, error, reset } = useMutation<
    StrategyGuideResponse,
    Error,
    StrategyGuideRequest | undefined
  >({
    mutationFn: (request) => getStrategyGuide(deckId, request),
  });

  return {
    generate: (request?: StrategyGuideRequest) => mutate(request),
    data,
    isPending,
    error,
    reset,
  };
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getDeck, listDecks, deleteDeck, buildDeck } from '../api/decks';
import type { DeckBuildRequest } from '../api/types';

/**
 * Fetch a single deck by ID.
 *
 * Usage:
 *   const { deck, isLoading, error } = useDeck(deckId);
 */
export function useDeck(deckId: number | null | undefined) {
  const query = useQuery({
    queryKey: ['deck', deckId],
    queryFn: () => getDeck(deckId!),
    enabled: deckId != null,
    staleTime: 60_000,
  });

  return {
    deck: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}

/**
 * Fetch the list of all saved decks.
 *
 * Usage:
 *   const { decks, isLoading } = useDeckList();
 */
export function useDeckList() {
  const query = useQuery({
    queryKey: ['decks'],
    queryFn: listDecks,
    staleTime: 30_000,
  });

  return {
    decks: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook to build a new deck.
 *
 * Usage:
 *   const { buildDeck, isBuilding, error, result } = useBuildDeck();
 *   buildDeck({ commander: 'Atraxa', budget: 200 });
 */
export function useBuildDeck() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: DeckBuildRequest) => buildDeck(request),
    onSuccess: () => {
      // Invalidate deck list so it refreshes after a new build
      queryClient.invalidateQueries({ queryKey: ['decks'] });
    },
  });

  return {
    buildDeck: mutation.mutate,
    buildDeckAsync: mutation.mutateAsync,
    isBuilding: mutation.isPending,
    error: mutation.error as Error | null,
    result: mutation.data ?? null,
    reset: mutation.reset,
  };
}

/**
 * Mutation hook to delete a deck.
 *
 * Usage:
 *   const { deleteDeck, isDeleting } = useDeleteDeck();
 *   deleteDeck(deckId);
 */
export function useDeleteDeck() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (id: number) => deleteDeck(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decks'] });
    },
  });

  return {
    deleteDeck: mutation.mutate,
    isDeleting: mutation.isPending,
    error: mutation.error as Error | null,
  };
}

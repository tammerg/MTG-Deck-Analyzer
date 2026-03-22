import { useMutation } from '@tanstack/react-query';
import { researchCommander } from '../api/research';
import type { ResearchRequest, ResearchResponse } from '../api/types';

/**
 * TanStack Query mutation hook for LLM commander research.
 *
 * Usage:
 *   const { research, isResearching, result, error, reset } = useResearch();
 *   research({ commander: 'Atraxa', budget: 200, provider: 'anthropic' });
 */
export function useResearch() {
  const mutation = useMutation<ResearchResponse, Error, ResearchRequest>({
    mutationFn: (request: ResearchRequest) => researchCommander(request),
  });

  return {
    research: mutation.mutate,
    researchAsync: mutation.mutateAsync,
    isResearching: mutation.isPending,
    result: mutation.data ?? null,
    error: mutation.error,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    reset: mutation.reset,
  };
}

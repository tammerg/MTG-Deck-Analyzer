import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getConfig, updateConfig, getHealth } from '../api/config';
import type { AppConfigUpdate } from '../api/types';

/**
 * TanStack Query hook for fetching and mutating application configuration.
 *
 * Usage:
 *   const { config, isLoading, saveConfig, isSaving } = useConfig();
 */
export function useConfig() {
  const queryClient = useQueryClient();

  const configQuery = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: (updates: AppConfigUpdate) => updateConfig(updates),
    onSuccess: (data) => {
      queryClient.setQueryData(['config'], data);
    },
  });

  return {
    config: configQuery.data ?? null,
    isLoading: configQuery.isLoading,
    error: configQuery.error as Error | null,
    refetch: configQuery.refetch,
    saveConfig: mutation.mutate,
    saveConfigAsync: mutation.mutateAsync,
    isSaving: mutation.isPending,
    saveError: mutation.error as Error | null,
    isSaveSuccess: mutation.isSuccess,
    reset: mutation.reset,
  };
}

/**
 * TanStack Query hook for fetching health status.
 * Polls every 10 seconds when the component is mounted.
 *
 * Usage:
 *   const { health, isLoading } = useHealth();
 */
export function useHealth() {
  const query = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  return {
    health: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}

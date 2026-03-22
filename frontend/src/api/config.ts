import api from './client';
import type { AppConfig, AppConfigUpdate, HealthResponse } from './types';

/**
 * Fetch application configuration.
 */
export async function getConfig(): Promise<AppConfig> {
  const { data } = await api.get<AppConfig>('/config');
  return data;
}

/**
 * Update application configuration using PUT with nested config shape.
 *
 * Usage:
 *   await updateConfig({ constraints: { max_price_per_card: 50 }, llm: { provider: 'openai' } });
 */
export async function updateConfig(update: AppConfigUpdate): Promise<AppConfig> {
  const { data } = await api.put<AppConfig>('/config', update);
  return data;
}

/**
 * Health check endpoint.
 */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health');
  return data;
}

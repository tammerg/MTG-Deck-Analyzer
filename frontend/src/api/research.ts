import api from './client';
import type { ResearchRequest, ResearchResponse } from './types';

/**
 * Research a commander using LLM analysis.
 *
 * Usage:
 *   const analysis = await researchCommander({ commander: 'Atraxa', budget: 200 });
 */
export async function researchCommander(request: ResearchRequest): Promise<ResearchResponse> {
  const { data } = await api.post<ResearchResponse>('/research', request);
  return data;
}

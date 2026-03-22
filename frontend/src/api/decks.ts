import api from './client';
import type { DeckBuildRequest, DeckResponse, DeckListItem, DeckExportFormat, DeckExportResponse, AdviseRequest, DeckAdviseResponse } from './types';

/**
 * Build a new deck from a commander name and budget.
 *
 * Usage:
 *   const deck = await buildDeck({ commander: 'Atraxa', budget: 200 });
 */
export async function buildDeck(request: DeckBuildRequest): Promise<DeckResponse> {
  const { data } = await api.post<DeckResponse>('/decks/build', request);
  return data;
}

/**
 * List all saved decks.
 */
export async function listDecks(): Promise<DeckListItem[]> {
  const { data } = await api.get<DeckListItem[]>('/decks');
  return data;
}

/**
 * Fetch a single deck by ID with full card details.
 */
export async function getDeck(id: number): Promise<DeckResponse> {
  const { data } = await api.get<DeckResponse>(`/decks/${id}`);
  return data;
}

/**
 * Delete a deck by ID.
 */
export async function deleteDeck(id: number): Promise<void> {
  await api.delete(`/decks/${id}`);
}

/**
 * Export a deck in the requested format via POST.
 *
 * Backend supports: csv, moxfield, archidekt
 * Returns the export response with content string.
 */
export async function exportDeck(id: number, format: DeckExportFormat = 'csv'): Promise<DeckExportResponse> {
  const { data } = await api.post<DeckExportResponse>(`/decks/${id}/export`, { format });
  return data;
}

/**
 * Ask an AI advisor about a specific deck.
 *
 * Usage:
 *   const response = await adviseDeck(42, 'How can I improve the mana curve?', 'anthropic');
 */
export async function adviseDeck(id: number, question: string, provider?: string): Promise<DeckAdviseResponse> {
  const body: AdviseRequest = { question, ...(provider ? { provider } : {}) };
  const { data } = await api.post<DeckAdviseResponse>(`/decks/${id}/advise`, body);
  return data;
}

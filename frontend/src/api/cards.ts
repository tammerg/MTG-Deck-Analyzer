import api from './client';
import type { CardResponse, CardSearchParams, CardSearchResponse, PopularCommandersListResponse, PrintingResponse } from './types';

/**
 * Search cards by query string with optional filters.
 *
 * Usage:
 *   const { results, total } = await searchCards({ q: 'Atraxa', color: 'WUBG', limit: 20 });
 */
export async function searchCards(params: CardSearchParams): Promise<CardSearchResponse> {
  const { data } = await api.get<CardSearchResponse>('/cards/search', { params });
  return data;
}

/**
 * Fetch a single card by its database ID.
 */
export async function getCard(id: number): Promise<CardResponse> {
  const { data } = await api.get<CardResponse>(`/cards/${id}`);
  return data;
}

/**
 * Get alternate printings for a card by its database card_id.
 */
export async function getCardPrintings(cardId: number): Promise<PrintingResponse[]> {
  const { data } = await api.get<PrintingResponse[]>(`/cards/${cardId}/printings`);
  return data;
}

/**
 * Get the current price for a card.
 */
export async function getCardPrice(id: number): Promise<{ card_id: number; card_name: string; price: number; currency: string; finish: string }> {
  const { data } = await api.get<{ card_id: number; card_name: string; price: number; currency: string; finish: string }>(`/cards/${id}/price`);
  return data;
}

/**
 * Search specifically for legal commanders.
 *
 * Usage:
 *   const commanders = await searchCommanders('Atraxa');
 */
export async function searchCommanders(query: string, limit = 20): Promise<CardResponse[]> {
  const { data } = await api.get<CardResponse[]>('/commanders/search', {
    params: { q: query, limit },
  });
  return data;
}

/**
 * Fetch popular commanders from EDHREC, sorted by deck count.
 */
export async function getPopularCommanders(limit = 20): Promise<PopularCommandersListResponse> {
  const { data } = await api.get<PopularCommandersListResponse>('/commanders/popular', {
    params: { limit },
  });
  return data;
}

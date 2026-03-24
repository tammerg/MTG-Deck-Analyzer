import type { DeckCardResponse } from '../api/types';

export type Marketplace = 'tcgplayer' | 'cardkingdom';

export interface MarketplaceOption {
  marketplace: Marketplace;
  label: string;
  price: number | null;
  url: string | null;
}

/**
 * Build a purchase URL for a single card on the given marketplace.
 */
export function getCardPurchaseUrl(
  marketplace: Marketplace,
  card: DeckCardResponse,
): string | null {
  switch (marketplace) {
    case 'tcgplayer':
      return card.tcgplayer_id
        ? `https://www.tcgplayer.com/product/${card.tcgplayer_id}`
        : null;
    case 'cardkingdom':
      return `https://www.cardkingdom.com/catalog/search?search=header&filter[name]=${encodeURIComponent(card.card_name)}`;
  }
}

/**
 * Build a bulk purchase URL for an entire deck on the given marketplace.
 */
export function getDeckPurchaseUrl(
  marketplace: Marketplace,
  cards: DeckCardResponse[],
): string {
  const entries = cards.map(
    (c) => `${c.quantity} ${c.card_name}`,
  );

  switch (marketplace) {
    case 'tcgplayer':
      return `https://www.tcgplayer.com/massentry?productline=magic&c=${encodeURIComponent(entries.join('||'))}`;
    case 'cardkingdom':
      return `https://www.cardkingdom.com/builder?partner=MTGDeckMaker&c=${encodeURIComponent(entries.join('\n'))}`;
  }
}

/**
 * Get per-card price for a specific marketplace source.
 * Both marketplaces use the same TCGPlayer-sourced USD price from Scryfall.
 */
export function getMarketplacePrice(
  _marketplace: Marketplace,
  card: DeckCardResponse,
): number | null {
  return card.price_tcgplayer ?? null;
}

/**
 * Compute total deck price for a given marketplace.
 * Returns null if no cards have prices for that source.
 */
export function getDeckTotalForMarketplace(
  marketplace: Marketplace,
  cards: DeckCardResponse[],
): number | null {
  let total = 0;
  let hasAny = false;

  for (const card of cards) {
    const p = getMarketplacePrice(marketplace, card);
    if (p != null) {
      total += p * card.quantity;
      hasAny = true;
    }
  }

  return hasAny ? Math.round(total * 100) / 100 : null;
}

/**
 * Recommend the cheapest marketplace for a deck.
 * Returns null if no marketplace has pricing data.
 */
export function recommendMarketplace(
  cards: DeckCardResponse[],
): Marketplace | null {
  const marketplaces: Marketplace[] = ['tcgplayer', 'cardkingdom'];
  let best: Marketplace | null = null;
  let bestTotal = Infinity;

  for (const m of marketplaces) {
    const total = getDeckTotalForMarketplace(m, cards);
    if (total != null && total < bestTotal) {
      bestTotal = total;
      best = m;
    }
  }

  return best;
}

/**
 * Get all marketplace options for a single card with URLs and prices.
 */
export function getCardMarketplaceOptions(
  card: DeckCardResponse,
): MarketplaceOption[] {
  const marketplaces: { marketplace: Marketplace; label: string }[] = [
    { marketplace: 'tcgplayer', label: 'TCGPlayer' },
    { marketplace: 'cardkingdom', label: 'Card Kingdom' },
  ];

  return marketplaces.map(({ marketplace, label }) => ({
    marketplace,
    label,
    price: getMarketplacePrice(marketplace, card),
    url: getCardPurchaseUrl(marketplace, card),
  }));
}

/** Human-friendly marketplace display names. */
export const MARKETPLACE_LABELS: Record<Marketplace, string> = {
  tcgplayer: 'TCGPlayer',
  cardkingdom: 'Card Kingdom',
};

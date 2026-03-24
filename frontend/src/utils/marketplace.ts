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
 *
 * @remarks
 * Currently always returns `'tcgplayer'` when pricing data is available because
 * {@link getMarketplacePrice} returns the same TCGPlayer-sourced USD price for
 * every marketplace. The "Best Price" recommendation is therefore meaningless
 * until distinct per-marketplace pricing is available. Do not surface this
 * result in the UI until that data is provided.
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
 * Single source of truth for marketplace metadata.
 * Add fields here (e.g. logoUrl, affiliateTag) as needed.
 */
export const MARKETPLACE_META: Record<Marketplace, { label: string }> = {
  tcgplayer: { label: 'TCGPlayer' },
  cardkingdom: { label: 'Card Kingdom' },
};

/** Human-friendly marketplace display names, derived from MARKETPLACE_META. */
export const MARKETPLACE_LABELS: Record<Marketplace, string> = {
  tcgplayer: MARKETPLACE_META.tcgplayer.label,
  cardkingdom: MARKETPLACE_META.cardkingdom.label,
};

/**
 * Get all marketplace options for a single card with URLs and prices.
 * Labels are derived from MARKETPLACE_META.
 */
export function getCardMarketplaceOptions(
  card: DeckCardResponse,
): MarketplaceOption[] {
  const marketplaces: Marketplace[] = ['tcgplayer', 'cardkingdom'];

  return marketplaces.map((marketplace) => ({
    marketplace,
    label: MARKETPLACE_META[marketplace].label,
    price: getMarketplacePrice(marketplace, card),
    url: getCardPurchaseUrl(marketplace, card),
  }));
}

import { describe, it, expect } from 'vitest';
import type { DeckCardResponse } from '../../api/types';
import {
  getCardPurchaseUrl,
  getDeckPurchaseUrl,
  getMarketplacePrice,
  getDeckTotalForMarketplace,
  recommendMarketplace,
  getCardMarketplaceOptions,
} from '../marketplace';

function makeCard(overrides: Partial<DeckCardResponse> = {}): DeckCardResponse {
  return {
    card_id: 1,
    quantity: 1,
    category: 'utility',
    is_commander: false,
    card_name: 'Sol Ring',
    cmc: 1,
    colors: [],
    price: 3.0,
    mana_cost: '{1}',
    type_line: 'Artifact',
    oracle_text: '{T}: Add {C}{C}.',
    image_url: null,
    tcgplayer_id: 12345,
    price_tcgplayer: 2.99,
    ...overrides,
  };
}

describe('getCardPurchaseUrl', () => {
  it('returns TCGPlayer URL with ID', () => {
    const url = getCardPurchaseUrl('tcgplayer', makeCard());
    expect(url).toBe('https://www.tcgplayer.com/product/12345');
  });

  it('returns null for TCGPlayer when no ID', () => {
    const url = getCardPurchaseUrl('tcgplayer', makeCard({ tcgplayer_id: null }));
    expect(url).toBeNull();
  });

  it('returns Card Kingdom search URL', () => {
    const url = getCardPurchaseUrl('cardkingdom', makeCard());
    expect(url).toContain('cardkingdom.com');
    expect(url).toContain('Sol%20Ring');
  });
});

describe('getDeckPurchaseUrl', () => {
  it('builds TCGPlayer mass entry URL', () => {
    const cards = [makeCard(), makeCard({ card_name: 'Arcane Signet', quantity: 1 })];
    const url = getDeckPurchaseUrl('tcgplayer', cards);
    expect(url).toContain('tcgplayer.com/massentry');
    expect(url).toContain('Sol%20Ring');
    expect(url).toContain('Arcane%20Signet');
  });

  it('builds Card Kingdom builder URL', () => {
    const url = getDeckPurchaseUrl('cardkingdom', [makeCard()]);
    expect(url).toContain('cardkingdom.com/builder');
  });
});

describe('getMarketplacePrice', () => {
  it('returns tcgplayer price', () => {
    expect(getMarketplacePrice('tcgplayer', makeCard())).toBe(2.99);
  });

  it('returns tcgplayer price for cardkingdom too', () => {
    expect(getMarketplacePrice('cardkingdom', makeCard())).toBe(2.99);
  });

  it('returns null when price missing', () => {
    expect(getMarketplacePrice('tcgplayer', makeCard({ price_tcgplayer: null }))).toBeNull();
  });
});

describe('getDeckTotalForMarketplace', () => {
  it('sums prices across cards with quantities', () => {
    const cards = [
      makeCard({ price_tcgplayer: 2.99, quantity: 1 }),
      makeCard({ price_tcgplayer: 1.50, quantity: 2 }),
    ];
    expect(getDeckTotalForMarketplace('tcgplayer', cards)).toBe(5.99);
  });

  it('returns null when no prices available', () => {
    const cards = [makeCard({ price_tcgplayer: null })];
    expect(getDeckTotalForMarketplace('tcgplayer', cards)).toBeNull();
  });
});

describe('recommendMarketplace', () => {
  it('recommends a marketplace when prices exist', () => {
    const cards = [makeCard({ price_tcgplayer: 5.00 })];
    const result = recommendMarketplace(cards);
    expect(result).not.toBeNull();
  });

  it('returns null when no prices', () => {
    const cards = [makeCard({ price_tcgplayer: null })];
    expect(recommendMarketplace(cards)).toBeNull();
  });
});

describe('getCardMarketplaceOptions', () => {
  it('returns 2 marketplace options', () => {
    const options = getCardMarketplaceOptions(makeCard());
    expect(options).toHaveLength(2);
    expect(options.map((o) => o.marketplace)).toEqual(['tcgplayer', 'cardkingdom']);
  });

  it('includes prices and URLs', () => {
    const options = getCardMarketplaceOptions(makeCard());
    const tcg = options.find((o) => o.marketplace === 'tcgplayer')!;
    expect(tcg.price).toBe(2.99);
    expect(tcg.url).toContain('tcgplayer.com');
  });
});

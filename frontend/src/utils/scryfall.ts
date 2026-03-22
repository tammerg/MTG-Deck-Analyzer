/**
 * Scryfall CDN utility functions.
 *
 * Scryfall image URL pattern:
 *   https://cards.scryfall.io/{size}/front/{id[0]}/{id[1]}/{scryfall_id}.jpg
 *
 * Mana symbol SVG URL pattern:
 *   https://svgs.scryfall.io/card-symbols/{SYMBOL}.svg
 */

export type ImageSize = 'small' | 'normal' | 'large' | 'png' | 'art_crop' | 'border_crop';

/**
 * Construct a Scryfall CDN image URL from a Scryfall card ID.
 *
 * Usage:
 *   getImageUrl('abc123de-...', 'normal')
 *   // → 'https://cards.scryfall.io/normal/front/a/b/abc123de-....jpg'
 */
export function getImageUrl(scryfallId: string, size: ImageSize = 'normal'): string {
  if (!scryfallId || scryfallId.length < 2) {
    return '';
  }
  const dir1 = scryfallId[0];
  const dir2 = scryfallId[1];
  return `https://cards.scryfall.io/${size}/front/${dir1}/${dir2}/${scryfallId}.jpg`;
}

/**
 * Parse mana cost string into an array of symbol strings.
 *
 * Usage:
 *   parseManaSymbols('{2}{W}{U}') → ['2', 'W', 'U']
 *   parseManaSymbols('{B/G}')     → ['B/G']
 */
export function parseManaSymbols(manaCost: string): string[] {
  if (!manaCost) return [];
  const matches = manaCost.match(/\{([^}]+)\}/g);
  if (!matches) return [];
  return matches.map((m) => m.slice(1, -1));
}

/**
 * Construct the Scryfall SVG URL for a mana symbol.
 *
 * Usage:
 *   getManaSymbolUrl('W')    → 'https://svgs.scryfall.io/card-symbols/W.svg'
 *   getManaSymbolUrl('2')    → 'https://svgs.scryfall.io/card-symbols/2.svg'
 *   getManaSymbolUrl('B/G')  → 'https://svgs.scryfall.io/card-symbols/BG.svg'
 */
export function getManaSymbolUrl(symbol: string): string {
  // Scryfall SVG filenames use no slash: B/G → BG
  const normalized = symbol.replace('/', '');
  return `https://svgs.scryfall.io/card-symbols/${normalized}.svg`;
}

/**
 * Extract Scryfall ID from a Scryfall image URL (reverse lookup).
 */
export function extractScryfallId(imageUrl: string): string | null {
  const match = imageUrl.match(/([0-9a-f-]{36})\.jpg/);
  return match ? match[1] : null;
}

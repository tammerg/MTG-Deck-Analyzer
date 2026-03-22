import { describe, it, expect } from 'vitest';
import { getImageUrl, parseManaSymbols, getManaSymbolUrl, extractScryfallId } from '../scryfall';

describe('getImageUrl', () => {
  it('constructs a normal-size URL from a Scryfall ID', () => {
    const id = 'abc12345-6789-abcd-ef01-234567890abc';
    expect(getImageUrl(id)).toBe(
      `https://cards.scryfall.io/normal/front/a/b/${id}.jpg`,
    );
  });

  it('supports different sizes', () => {
    const id = 'abc12345-6789-abcd-ef01-234567890abc';
    expect(getImageUrl(id, 'large')).toContain('/large/front/');
  });

  it('returns empty string for empty ID', () => {
    expect(getImageUrl('')).toBe('');
  });

  it('returns empty string for short ID', () => {
    expect(getImageUrl('a')).toBe('');
  });
});

describe('parseManaSymbols', () => {
  it('parses a standard mana cost', () => {
    expect(parseManaSymbols('{2}{W}{U}')).toEqual(['2', 'W', 'U']);
  });

  it('parses hybrid mana', () => {
    expect(parseManaSymbols('{B/G}')).toEqual(['B/G']);
  });

  it('returns empty array for empty string', () => {
    expect(parseManaSymbols('')).toEqual([]);
  });

  it('returns empty array for string without braces', () => {
    expect(parseManaSymbols('2WU')).toEqual([]);
  });
});

describe('getManaSymbolUrl', () => {
  it('constructs a URL for a simple symbol', () => {
    expect(getManaSymbolUrl('W')).toBe('https://svgs.scryfall.io/card-symbols/W.svg');
  });

  it('strips slash from hybrid symbols', () => {
    expect(getManaSymbolUrl('B/G')).toBe('https://svgs.scryfall.io/card-symbols/BG.svg');
  });

  it('handles numeric symbols', () => {
    expect(getManaSymbolUrl('2')).toBe('https://svgs.scryfall.io/card-symbols/2.svg');
  });
});

describe('extractScryfallId', () => {
  it('extracts a UUID from an image URL', () => {
    const url = 'https://cards.scryfall.io/normal/front/a/b/abc12345-6789-abcd-ef01-234567890abc.jpg';
    expect(extractScryfallId(url)).toBe('abc12345-6789-abcd-ef01-234567890abc');
  });

  it('returns null for non-matching URL', () => {
    expect(extractScryfallId('https://example.com/image.png')).toBeNull();
  });
});

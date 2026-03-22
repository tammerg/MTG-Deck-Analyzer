import { describe, it, expect } from 'vitest';
import { getCategoryDisplayName, getCategoryColor, getCategorySortOrder } from '../categories';

describe('getCategoryDisplayName', () => {
  it('returns display name for known categories', () => {
    expect(getCategoryDisplayName('ramp')).toBe('Ramp');
    expect(getCategoryDisplayName('draw')).toBe('Card Draw');
    expect(getCategoryDisplayName('win_condition')).toBe('Win Condition');
    expect(getCategoryDisplayName('boardwipe')).toBe('Board Wipe');
  });

  it('capitalizes unknown categories', () => {
    expect(getCategoryDisplayName('custom_thing')).toBe('Custom thing');
  });

  it('returns Unknown for empty string', () => {
    expect(getCategoryDisplayName('')).toBe('Unknown');
  });
});

describe('getCategoryColor', () => {
  it('returns correct color classes for known categories', () => {
    expect(getCategoryColor('ramp')).toContain('bg-green');
    expect(getCategoryColor('draw')).toContain('bg-blue');
    expect(getCategoryColor('removal')).toContain('bg-red');
  });

  it('returns fallback for unknown categories', () => {
    expect(getCategoryColor('unknown_cat')).toContain('bg-slate');
  });
});

describe('getCategorySortOrder', () => {
  it('puts commander first', () => {
    expect(getCategorySortOrder('commander')).toBe(0);
  });

  it('puts basic_land last', () => {
    expect(getCategorySortOrder('basic_land')).toBe(18);
  });

  it('returns 99 for unknown categories', () => {
    expect(getCategorySortOrder('unknown')).toBe(99);
  });

  it('orders ramp before removal', () => {
    expect(getCategorySortOrder('ramp')).toBeLessThan(getCategorySortOrder('removal'));
  });
});

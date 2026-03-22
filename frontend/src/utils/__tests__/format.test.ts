import { describe, it, expect } from 'vitest';
import { formatPrice, formatColorName, formatDate, formatCmc, truncate } from '../format';

describe('formatPrice', () => {
  it('formats a number as USD', () => {
    expect(formatPrice(1.5)).toBe('$1.50');
  });

  it('formats zero', () => {
    expect(formatPrice(0)).toBe('$0.00');
  });

  it('returns N/A for null', () => {
    expect(formatPrice(null)).toBe('N/A');
  });

  it('returns N/A for undefined', () => {
    expect(formatPrice(undefined)).toBe('N/A');
  });

  it('formats large numbers with commas', () => {
    expect(formatPrice(1234.56)).toBe('$1,234.56');
  });
});

describe('formatColorName', () => {
  it('maps W to White', () => {
    expect(formatColorName('W')).toBe('White');
  });

  it('maps U to Blue', () => {
    expect(formatColorName('U')).toBe('Blue');
  });

  it('maps B to Black', () => {
    expect(formatColorName('B')).toBe('Black');
  });

  it('maps R to Red', () => {
    expect(formatColorName('R')).toBe('Red');
  });

  it('maps G to Green', () => {
    expect(formatColorName('G')).toBe('Green');
  });

  it('maps C to Colorless', () => {
    expect(formatColorName('C')).toBe('Colorless');
  });

  it('handles lowercase input', () => {
    expect(formatColorName('w')).toBe('White');
  });

  it('returns unknown codes as-is', () => {
    expect(formatColorName('X')).toBe('X');
  });
});

describe('formatDate', () => {
  it('formats an ISO date string', () => {
    const result = formatDate('2024-01-15T12:00:00Z');
    expect(result).toContain('Jan');
    expect(result).toContain('15');
    expect(result).toContain('2024');
  });
});

describe('formatCmc', () => {
  it('formats an integer without decimals', () => {
    expect(formatCmc(3)).toBe('3');
  });

  it('formats a decimal with one place', () => {
    expect(formatCmc(2.5)).toBe('2.5');
  });

  it('formats zero', () => {
    expect(formatCmc(0)).toBe('0');
  });
});

describe('truncate', () => {
  it('returns short strings unchanged', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('truncates long strings with ellipsis', () => {
    expect(truncate('hello world', 6)).toBe('hello\u2026');
  });

  it('handles exact length', () => {
    expect(truncate('hello', 5)).toBe('hello');
  });
});

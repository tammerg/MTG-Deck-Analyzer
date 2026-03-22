/**
 * Formatting utility functions for display values.
 */

/**
 * Format a price number as a USD string.
 *
 * Usage:
 *   formatPrice(1.5)   → '$1.50'
 *   formatPrice(0)     → '$0.00'
 *   formatPrice(null)  → 'N/A'
 */
export function formatPrice(price: number | null | undefined): string {
  if (price == null) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price);
}

/**
 * Map a single-letter WUBRG color code to its full English name.
 *
 * Usage:
 *   formatColorName('W') → 'White'
 *   formatColorName('U') → 'Blue'
 */
export function formatColorName(color: string): string {
  const names: Record<string, string> = {
    W: 'White',
    U: 'Blue',
    B: 'Black',
    R: 'Red',
    G: 'Green',
    C: 'Colorless',
  };
  return names[color.toUpperCase()] ?? color;
}

/**
 * Format a date string into a human-readable local date.
 *
 * Usage:
 *   formatDate('2024-01-15T12:00:00Z') → 'Jan 15, 2024'
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

/**
 * Format CMC as a readable string.
 *
 * Usage:
 *   formatCmc(2.5) → '2.5'
 *   formatCmc(3)   → '3'
 */
export function formatCmc(cmc: number): string {
  return Number.isInteger(cmc) ? cmc.toString() : cmc.toFixed(1);
}

/**
 * Truncate a string to a maximum length with ellipsis.
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 1) + '\u2026';
}

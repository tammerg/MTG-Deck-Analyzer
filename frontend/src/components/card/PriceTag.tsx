import { formatPrice } from '../../utils/format';

interface PriceTagProps {
  price: number | null | undefined;
  /** Optional budget cap for color-coding */
  budget?: number;
  className?: string;
}

/**
 * Displays a price with budget-aware color coding.
 *
 * Color rules:
 *   - No budget provided: neutral text
 *   - price <= budget * 0.8: green (ok)
 *   - price <= budget: yellow (warn)
 *   - price > budget: red (over)
 *
 * Usage:
 *   <PriceTag price={1.50} />
 *   <PriceTag price={card.price} budget={200} />
 */
export default function PriceTag({ price, budget, className = '' }: PriceTagProps) {
  const colorClass = getPriceColorClass(price, budget);

  return (
    <span
      className={['text-sm font-mono font-medium', colorClass, className].join(' ')}
      aria-label={`Price: ${formatPrice(price)}`}
    >
      {formatPrice(price)}
    </span>
  );
}

function getPriceColorClass(price: number | null | undefined, budget?: number): string {
  if (price == null) return 'text-[var(--color-text-secondary)]';
  if (budget == null) return 'text-[var(--color-text-primary)]';

  if (price > budget) return 'text-[var(--color-budget-over)]';
  if (price > budget * 0.8) return 'text-[var(--color-budget-warn)]';
  return 'text-[var(--color-budget-ok)]';
}

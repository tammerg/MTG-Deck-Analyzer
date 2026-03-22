import { formatPrice } from '../../utils/format';

interface DeckStatsProps {
  totalCards: number;
  totalPrice: number;
  averageCmc: number;
  budgetTarget: number | null;
  format: string;
}

interface StatCardProps {
  label: string;
  value: string;
  highlight?: boolean;
}

/**
 * Grid of key deck statistics: card count, price, avg CMC, and budget remaining.
 *
 * Usage:
 *   <DeckStats
 *     totalCards={99}
 *     totalPrice={198.50}
 *     averageCmc={2.4}
 *     budgetTarget={200}
 *     format="commander"
 *   />
 */
export default function DeckStats({
  totalCards,
  totalPrice,
  averageCmc,
  budgetTarget,
  format,
}: DeckStatsProps) {
  const budgetRemaining = budgetTarget != null ? budgetTarget - totalPrice : null;
  const overBudget = budgetRemaining != null && budgetRemaining < 0;

  return (
    <div
      className="grid grid-cols-2 gap-3 sm:grid-cols-4"
      aria-label="Deck statistics"
    >
      <StatCard label="Total Cards" value={totalCards.toString()} />
      <StatCard label="Total Price" value={formatPrice(totalPrice)} />
      <StatCard label="Avg. CMC" value={averageCmc.toFixed(2)} />

      {budgetRemaining != null ? (
        <div
          className={[
            'flex flex-col items-center justify-center rounded-lg border px-4 py-3 text-center',
            overBudget
              ? 'border-[var(--color-budget-over)] bg-red-950'
              : 'border-[var(--color-border)] bg-[var(--color-surface-alt)]',
          ].join(' ')}
        >
          <span
            className={[
              'text-xl font-mono font-bold',
              overBudget
                ? 'text-[var(--color-budget-over)]'
                : 'text-[var(--color-budget-ok)]',
            ].join(' ')}
          >
            {overBudget ? '-' : '+'}{formatPrice(Math.abs(budgetRemaining))}
          </span>
          <span className="mt-1 text-xs text-[var(--color-text-secondary)]">
            {overBudget ? 'Over Budget' : 'Under Budget'}
          </span>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] px-4 py-3 text-center">
          <span className="text-xl font-mono font-bold capitalize text-[var(--color-text-primary)]">
            {format}
          </span>
          <span className="mt-1 text-xs text-[var(--color-text-secondary)]">Format</span>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, highlight }: StatCardProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] px-4 py-3 text-center">
      <span
        className={[
          'text-xl font-mono font-bold',
          highlight
            ? 'text-[var(--color-accent)]'
            : 'text-[var(--color-text-primary)]',
        ].join(' ')}
      >
        {value}
      </span>
      <span className="mt-1 text-xs text-[var(--color-text-secondary)]">{label}</span>
    </div>
  );
}

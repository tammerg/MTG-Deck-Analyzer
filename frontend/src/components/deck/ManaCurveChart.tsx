import type { DeckCardResponse } from '../../api/types';

interface ManaCurveChartProps {
  cards: DeckCardResponse[];
}

const CMC_LABELS = ['0', '1', '2', '3', '4', '5', '6', '7+'];

/** Purple gradient from light to dark — visually conveys increasing mana cost. */
const BAR_COLORS = [
  'bg-violet-300',
  'bg-violet-400',
  'bg-violet-500',
  'bg-purple-500',
  'bg-purple-600',
  'bg-purple-700',
  'bg-purple-800',
  'bg-purple-900',
];

/**
 * Simple bar chart showing the mana curve (CMC distribution) of deck cards.
 * Uses Tailwind div bars — no chart library required.
 *
 * Cards with CMC >= 7 are grouped into the "7+" bucket.
 *
 * Usage:
 *   <ManaCurveChart cards={deck.cards} />
 */
export default function ManaCurveChart({ cards }: ManaCurveChartProps) {
  // Build CMC distribution buckets 0-7 (7+)
  const buckets = Array<number>(8).fill(0);

  cards
    .filter((c) => !c.is_commander)
    .forEach((card) => {
      const bucket = Math.min(Math.floor(card.cmc), 7);
      buckets[bucket] += card.quantity;
    });

  const maxCount = Math.max(...buckets, 1);

  return (
    <section aria-labelledby="mana-curve-heading" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-4">
      <h3
        id="mana-curve-heading"
        className="mb-4 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
      >
        Mana Curve
      </h3>

      <div
        className="flex h-32 gap-1.5"
        role="img"
        aria-label={`Mana curve: ${buckets.map((count, i) => `CMC ${CMC_LABELS[i]}: ${count} cards`).join(', ')}`}
      >
        {buckets.map((count, index) => {
          const heightPercent = maxCount > 0 ? (count / maxCount) * 100 : 0;

          return (
            <div
              key={index}
              className="flex flex-1 flex-col items-center justify-end gap-1"
              title={`CMC ${CMC_LABELS[index]}: ${count} card${count !== 1 ? 's' : ''}`}
            >
              {/* Count label above bar */}
              <span className="text-xs text-[var(--color-text-secondary)]" aria-hidden="true">
                {count > 0 ? count : ''}
              </span>

              {/* Bar */}
              <div
                className={[
                  'w-full rounded-t-sm transition-all duration-300',
                  BAR_COLORS[index],
                  count === 0 ? 'opacity-30' : '',
                ].join(' ')}
                style={{ height: `${Math.max(heightPercent, count > 0 ? 4 : 0)}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* CMC labels */}
      <div className="mt-1 flex gap-1.5" aria-hidden="true">
        {CMC_LABELS.map((label, index) => (
          <div key={index} className="flex-1 text-center text-xs text-[var(--color-text-secondary)]">
            {label}
          </div>
        ))}
      </div>
    </section>
  );
}

import { formatColorName } from '../../utils/format';

interface ColorDistributionProps {
  /** Record of color letter → card count, e.g. { W: 12, U: 18, B: 5 } */
  colorDistribution: Record<string, number>;
}

const WUBRG_ORDER = ['W', 'U', 'B', 'R', 'G'];

const COLOR_STYLES: Record<string, { bar: string; label: string }> = {
  W: { bar: 'bg-[var(--color-mana-w)]', label: 'White' },
  U: { bar: 'bg-[var(--color-mana-u)]', label: 'Blue' },
  B: { bar: 'bg-[#3d2b1f]', label: 'Black' },
  R: { bar: 'bg-[var(--color-mana-r)]', label: 'Red' },
  G: { bar: 'bg-[var(--color-mana-g)]', label: 'Green' },
  C: { bar: 'bg-gray-500', label: 'Colorless' },
};

/**
 * Horizontal bar breakdown of color distribution in the deck.
 * Proportional bars representing each color's share of the total.
 *
 * Usage:
 *   <ColorDistribution colorDistribution={deck.color_distribution} />
 */
export default function ColorDistribution({ colorDistribution }: ColorDistributionProps) {
  // Build entries: WUBRG order first, then any extras (Colorless, etc.)
  const entries = WUBRG_ORDER
    .filter((color) => colorDistribution[color] != null)
    .map((color) => ({ color, count: colorDistribution[color] }));

  // Add non-WUBRG colors (e.g., C for colorless)
  Object.entries(colorDistribution).forEach(([color, count]) => {
    if (!WUBRG_ORDER.includes(color)) {
      entries.push({ color, count });
    }
  });

  if (entries.length === 0) {
    return null;
  }

  const total = entries.reduce((sum, e) => sum + e.count, 0);

  return (
    <section
      aria-labelledby="color-dist-heading"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-4"
    >
      <h3
        id="color-dist-heading"
        className="mb-4 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
      >
        Color Distribution
      </h3>

      <div className="space-y-2" role="list" aria-label="Color distribution bars">
        {entries.map(({ color, count }) => {
          const percent = total > 0 ? (count / total) * 100 : 0;
          const styles = COLOR_STYLES[color.toUpperCase()] ?? { bar: 'bg-gray-500', label: color };
          const displayName = formatColorName(color);

          return (
            <div
              key={color}
              role="listitem"
              aria-label={`${displayName}: ${count} cards (${percent.toFixed(0)}%)`}
              className="flex items-center gap-3"
            >
              {/* Color label */}
              <span
                className="w-16 shrink-0 text-xs text-[var(--color-text-secondary)]"
                aria-hidden="true"
              >
                {displayName}
              </span>

              {/* Bar track */}
              <div
                className="relative flex-1 h-3 overflow-hidden rounded-full bg-[var(--color-surface-raised)]"
                aria-hidden="true"
              >
                <div
                  className={['h-full rounded-full transition-all duration-500', styles.bar].join(' ')}
                  style={{ width: `${percent}%` }}
                />
              </div>

              {/* Count */}
              <span
                className="w-8 shrink-0 text-right text-xs font-mono text-[var(--color-text-secondary)]"
                aria-hidden="true"
              >
                {count}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

import { usePopularCommanders } from '../../hooks/usePopularCommanders';
import type { CardResponse } from '../../api/types';

interface PopularCommandersProps {
  onSelect: (card: CardResponse) => void;
}

export default function PopularCommanders({ onSelect }: PopularCommandersProps) {
  const { commanders, isLoading, error } = usePopularCommanders(20);

  if (error) {
    return (
      <section aria-label="Popular commanders">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Could not load popular commanders.
        </p>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section aria-label="Popular commanders">
        <h2 className="mb-3 text-lg font-semibold text-[var(--color-text-primary)]">
          Popular Commanders
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-lg bg-[var(--color-border)]"
            />
          ))}
        </div>
      </section>
    );
  }

  if (commanders.length === 0) {
    return null;
  }

  return (
    <section aria-label="Popular commanders">
      <h2 className="mb-3 text-lg font-semibold text-[var(--color-text-primary)]">
        Popular Commanders
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {commanders.map(({ card, num_decks }) => (
          <button
            key={card.id}
            type="button"
            onClick={() => onSelect(card)}
            className={[
              'group relative flex flex-col items-center overflow-hidden rounded-lg border',
              'border-[var(--color-border)] bg-[var(--color-surface-alt)]',
              'p-3 text-left transition-all',
              'hover:border-[var(--color-accent)] hover:shadow-md',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            {card.image_url && (
              <img
                src={card.image_url}
                alt={card.name}
                className="mb-2 h-20 w-auto rounded object-contain"
                loading="lazy"
              />
            )}
            <span className="line-clamp-2 text-center text-xs font-medium text-[var(--color-text-primary)]">
              {card.name}
            </span>
            <span className="mt-1 flex items-center gap-1">
              <ColorPips colors={card.color_identity} />
            </span>
            <span className="mt-1 text-[10px] text-[var(--color-text-secondary)]">
              {num_decks.toLocaleString()} decks
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function ColorPips({ colors }: { colors: string[] }) {
  if (colors.length === 0) {
    return <span className="text-[10px] text-[var(--color-text-secondary)]">C</span>;
  }

  const colorMap: Record<string, string> = {
    W: 'bg-amber-100 text-amber-800',
    U: 'bg-blue-200 text-blue-800',
    B: 'bg-gray-400 text-gray-900',
    R: 'bg-red-200 text-red-800',
    G: 'bg-green-200 text-green-800',
  };

  return (
    <>
      {colors.map((c) => (
        <span
          key={c}
          className={`inline-block h-3 w-3 rounded-full text-[8px] font-bold leading-3 text-center ${colorMap[c] ?? 'bg-gray-200 text-gray-600'}`}
          aria-label={c}
        >
          {c}
        </span>
      ))}
    </>
  );
}

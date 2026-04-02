import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { upgradeDeck } from '../../api/decks';
import type { DeckUpgradeResponse } from '../../api/types';

interface UpgradePanelProps {
  deckId: number;
}

const FOCUS_OPTIONS = [
  { value: '', label: 'Any' },
  { value: 'card_draw', label: 'Card Draw' },
  { value: 'ramp', label: 'Ramp' },
  { value: 'removal', label: 'Removal' },
  { value: 'board_wipe', label: 'Board Wipes' },
  { value: 'counter', label: 'Counters' },
  { value: 'protection', label: 'Protection' },
  { value: 'recursion', label: 'Recursion' },
  { value: 'win_condition', label: 'Win Conditions' },
  { value: 'tutor', label: 'Tutors' },
];

/**
 * Panel for getting upgrade recommendations for a deck.
 * Users set a budget and optional focus category, then see swap suggestions.
 *
 * Usage:
 *   <UpgradePanel deckId={42} />
 */
export default function UpgradePanel({ deckId }: UpgradePanelProps) {
  const [budget, setBudget] = useState(50);
  const [focus, setFocus] = useState('');

  const { mutate: getUpgrades, data, isPending, error, reset } = useMutation<
    DeckUpgradeResponse,
    Error,
    { budget: number; focus?: string }
  >({
    mutationFn: ({ budget: b, focus: f }) =>
      upgradeDeck(deckId, { budget: b, ...(f ? { focus: f } : {}) }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;
    reset();
    getUpgrades({ budget, focus: focus || undefined });
  };

  return (
    <section
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]"
      aria-label="Upgrade Recommendations"
    >
      {/* Header */}
      <div className="border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <UpgradeIcon />
          Upgrade Recommendations
        </h2>
        <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
          Find better cards within your budget.
        </p>
      </div>

      {/* Form */}
      <form
        onSubmit={handleSubmit}
        className="border-b border-[var(--color-border)] p-4 space-y-3"
        aria-label="Upgrade options"
      >
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label
              htmlFor={`upgrade-budget-${deckId}`}
              className="block text-xs text-[var(--color-text-secondary)] mb-1"
            >
              Budget ($)
            </label>
            <input
              id={`upgrade-budget-${deckId}`}
              type="number"
              min={1}
              step={1}
              value={budget}
              onChange={(e) => setBudget(Math.max(1, Number(e.target.value)))}
              disabled={isPending}
              className={[
                'w-24 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
                'px-2 py-1.5 text-sm text-[var(--color-text-primary)]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
                'disabled:opacity-50',
              ].join(' ')}
            />
          </div>

          <div>
            <label
              htmlFor={`upgrade-focus-${deckId}`}
              className="block text-xs text-[var(--color-text-secondary)] mb-1"
            >
              Focus Category
            </label>
            <select
              id={`upgrade-focus-${deckId}`}
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              disabled={isPending}
              className={[
                'rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
                'px-2 py-1.5 text-xs text-[var(--color-text-primary)]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
                'disabled:opacity-50',
              ].join(' ')}
            >
              {FOCUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={isPending}
            aria-busy={isPending}
            className={[
              'rounded-lg px-4 py-2 text-sm font-semibold transition-colors',
              'bg-[var(--color-accent)] text-white',
              'hover:bg-[var(--color-accent-hover)]',
              'disabled:cursor-not-allowed disabled:opacity-40',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            {isPending ? (
              <span className="flex items-center gap-2">
                <SpinnerIcon />
                Analyzing...
              </span>
            ) : (
              'Get Recommendations'
            )}
          </button>
        </div>
      </form>

      {/* Loading skeleton */}
      {isPending && (
        <div className="p-4 space-y-2" aria-label="Loading recommendations">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-md bg-[var(--color-border)]"
            />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="mx-4 my-3 rounded-md border border-[var(--color-budget-over)] bg-red-950/40 p-3 text-sm text-[var(--color-budget-over)]"
        >
          <strong className="block font-semibold">Error</strong>
          {error.message}
        </div>
      )}

      {/* Results */}
      {data && !isPending && (
        <div className="p-4 space-y-3">
          {data.recommendations.length === 0 ? (
            <p className="text-sm text-[var(--color-text-secondary)]">
              No upgrades found within the given budget.
            </p>
          ) : (
            <>
              <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                <span>{data.recommendations.length} recommendation{data.recommendations.length !== 1 ? 's' : ''}</span>
                <span>Total cost: ${data.total_cost.toFixed(2)}</span>
              </div>

              <ul className="space-y-2" aria-label="Upgrade recommendations">
                {data.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                  >
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-[var(--color-budget-over)] line-through">
                        {rec.card_out}
                      </span>
                      <ArrowIcon />
                      <span className="font-medium text-[var(--color-budget-under)]">
                        {rec.card_in}
                      </span>
                      <span className={[
                        'ml-auto text-xs font-mono',
                        rec.price_delta > 0
                          ? 'text-[var(--color-budget-over)]'
                          : 'text-[var(--color-budget-under)]',
                      ].join(' ')}>
                        {rec.price_delta > 0 ? '+' : ''}${rec.price_delta.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                      {rec.reason}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function UpgradeIcon() {
  return (
    <svg
      className="h-4 w-4 text-[var(--color-accent)]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      className="h-3 w-3 shrink-0 text-[var(--color-text-secondary)]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="h-3 w-3 animate-spin text-white"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}

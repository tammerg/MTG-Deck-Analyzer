import { useState, useEffect } from 'react';
import CommanderSearch from '../components/search/CommanderSearch';
import PopularCommanders from '../components/research/PopularCommanders';
import ResearchResultDisplay from '../components/research/ResearchResultDisplay';
import { useResearch } from '../hooks/useResearch';
import type { CardResponse } from '../api/types';

/**
 * Commander research page — data-driven or LLM-powered strategy analysis.
 *
 * Features:
 * - Commander autocomplete search
 * - Optional budget and provider selection
 * - Structured result display with collapsible sections
 * - Loading and error states
 */
export default function ResearchPage() {
  useEffect(() => {
    document.title = 'Research | MTG Deck Maker';
  }, []);

  const [commander, setCommander] = useState<CardResponse | null>(null);
  const [budget, setBudget] = useState<number | ''>('');
  const [provider, setProvider] = useState('data');

  const { research, isResearching, result, error, reset } = useResearch();

  const handleResearch = () => {
    if (!commander) return;
    reset();
    research({
      commander: commander.name,
      budget: budget !== '' ? budget : undefined,
      provider: provider || undefined,
    });
  };

  const handleCommanderSelect = (card: CardResponse) => {
    setCommander(card);
    reset();
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-12">
      <header>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
          Research a Commander
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          Analyze strategy, key cards, combos, and win conditions for any commander.
        </p>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Search Form                                                          */}
      {/* ------------------------------------------------------------------ */}
      <section
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-4"
        aria-label="Research form"
      >
        {/* Commander picker */}
        <div>
          <label
            htmlFor="commander-search-combobox"
            className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
          >
            Commander
          </label>
          <CommanderSearch
            onSelect={handleCommanderSelect}
            initialValue={commander?.name ?? ''}
            placeholder="Search for a commander..."
          />
        </div>

        {/* Budget + Provider row */}
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label
              htmlFor="research-budget"
              className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
            >
              Budget (USD, optional)
            </label>
            <div className="relative">
              <span
                className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--color-text-secondary)]"
                aria-hidden="true"
              >
                $
              </span>
              <input
                id="research-budget"
                type="number"
                min={0}
                step={10}
                value={budget}
                onChange={(e) =>
                  setBudget(e.target.value === '' ? '' : Number(e.target.value))
                }
                placeholder="200"
                className={[
                  'w-32 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
                  'pl-7 pr-3 py-2 text-sm text-[var(--color-text-primary)]',
                  'placeholder:text-[var(--color-text-secondary)]',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
                ].join(' ')}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="research-provider"
              className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
            >
              AI Provider
            </label>
            <select
              id="research-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className={[
                'rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
                'px-3 py-2 text-sm text-[var(--color-text-primary)]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
              ].join(' ')}
            >
              <option value="data">Free (Data-Driven)</option>
              <option value="">Auto</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
            </select>
          </div>

          {/* Submit */}
          <button
            type="button"
            onClick={handleResearch}
            disabled={!commander || isResearching}
            aria-busy={isResearching}
            className={[
              'ml-auto rounded-lg px-5 py-2 text-sm font-semibold transition-colors',
              'bg-[var(--color-accent)] text-white',
              'hover:bg-[var(--color-accent-hover)]',
              'disabled:cursor-not-allowed disabled:opacity-40',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            {isResearching ? (
              <span className="flex items-center gap-2">
                <SpinnerIcon />
                Researching {commander?.name ?? ''}...
              </span>
            ) : (
              'Research Commander'
            )}
          </button>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Popular commanders — shown when idle                                 */}
      {/* ------------------------------------------------------------------ */}
      {!result && !isResearching && !error && (
        <PopularCommanders onSelect={handleCommanderSelect} />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Loading state — shown when no result yet                             */}
      {/* ------------------------------------------------------------------ */}
      {isResearching && !result && (
        <ResearchSkeleton commanderName={commander?.name ?? 'commander'} />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Error state                                                          */}
      {/* ------------------------------------------------------------------ */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-[var(--color-budget-over)] bg-red-950/40 p-4"
        >
          <p className="text-sm font-semibold text-[var(--color-budget-over)]">
            Research failed
          </p>
          <p className="mt-1 text-sm text-[var(--color-budget-over)]/80">
            {isLLMUnavailableError(error)
              ? 'No LLM provider is configured. Please add an API key in Settings before using research.'
              : error.message}
          </p>
          <button
            type="button"
            onClick={handleResearch}
            className="mt-3 text-xs underline text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            Try again
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Results                                                              */}
      {/* ------------------------------------------------------------------ */}
      {result && <ResearchResultDisplay result={result} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ResearchSkeleton — shown while request is in flight before first result
// ---------------------------------------------------------------------------

function ResearchSkeleton({ commanderName }: { commanderName: string }) {
  return (
    <div
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-4"
      aria-busy="true"
      aria-label={`Researching ${commanderName}`}
    >
      <div className="flex items-center gap-3">
        <SpinnerIcon className="h-5 w-5 text-[var(--color-accent)]" />
        <p className="text-sm font-medium text-[var(--color-text-secondary)]">
          Researching <span className="text-[var(--color-text-primary)]">{commanderName}</span>...
        </p>
      </div>
      <div className="space-y-3">
        {[80, 65, 90, 50].map((w, i) => (
          <div
            key={i}
            className="h-3 animate-pulse rounded bg-[var(--color-border)]"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SpinnerIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg
      className={['animate-spin text-white', className].join(' ')}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

function isLLMUnavailableError(error: Error): boolean {
  const msg = error.message.toLowerCase();
  return (
    msg.includes('no provider') ||
    msg.includes('not configured') ||
    msg.includes('provider unavailable') ||
    msg.includes('api key') ||
    msg.includes('503') ||
    msg.includes('424')
  );
}

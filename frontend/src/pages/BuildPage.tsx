import { useState, useEffect } from 'react';
import { useLocation, useNavigate, Link } from 'react-router';
import BuildConfigForm, { type BuildConfig } from '../components/build/BuildConfigForm';
import { useBuildDeck } from '../hooks/useDeck';
import type { CardResponse } from '../api/types';

interface LocationState {
  commander?: CardResponse;
}

const DEFAULT_CONFIG: BuildConfig = {
  budget: 100,
  smart: true,
  provider: '',
  seed: '',
};

const BUILD_MESSAGES = [
  'Analyzing commander strategies...',
  'Selecting ramp and mana base...',
  'Choosing card draw engines...',
  'Adding interaction and removal...',
  'Optimizing for budget...',
  'Finalizing deck list...',
];

/**
 * Full deck build page.
 * Steps: commander selection → configuration → build → redirect to deck view.
 *
 * Pre-populates commander if navigated from HomePage with location state.
 */
export default function BuildPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const locationState = location.state as LocationState | null;

  const [commander, setCommander] = useState<CardResponse | null>(
    locationState?.commander ?? null
  );
  const [partner, setPartner] = useState<CardResponse | null>(null);
  const [config, setConfig] = useState<BuildConfig>(DEFAULT_CONFIG);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    document.title = 'Build Deck | MTG Deck Maker';
  }, []);

  const { buildDeckAsync, isBuilding, error, reset } = useBuildDeck();

  // Cycle through progress messages while building
  const startMessageCycle = () => {
    setMessageIndex(0);
    const interval = setInterval(() => {
      setMessageIndex((prev) => {
        const next = prev + 1;
        if (next >= BUILD_MESSAGES.length - 1) {
          clearInterval(interval);
        }
        return next;
      });
    }, 2500);
    return interval;
  };

  const handleBuild = async () => {
    if (!commander) return;
    reset();
    const interval = startMessageCycle();
    try {
      const deck = await buildDeckAsync({
        commander: commander.name,
        partner: partner?.name,
        budget: config.budget,
        smart: config.smart,
        provider: config.provider || undefined,
        seed: config.seed ? parseInt(config.seed, 10) : undefined,
      });
      clearInterval(interval);
      navigate(`/deck/${deck.id}`);
    } catch {
      clearInterval(interval);
      // error is captured in useBuildDeck
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      {/* Page header */}
      <div className="mb-8">
        <nav className="mb-2 text-sm" aria-label="Breadcrumb">
          <Link
            to="/"
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            Home
          </Link>
          <span className="mx-2 text-[var(--color-text-secondary)]" aria-hidden="true">/</span>
          <span className="text-[var(--color-text-primary)]">Build</span>
        </nav>
        <h1 className="text-3xl font-bold text-[var(--color-text-primary)]">Build a Deck</h1>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          Choose a commander and configure your deck parameters below.
        </p>
      </div>

      {/* Build form */}
      <BuildConfigForm
        commander={commander}
        onCommanderChange={(card) => {
          setCommander(card);
          reset();
        }}
        partner={partner}
        onPartnerChange={setPartner}
        config={config}
        onConfigChange={(updates) => setConfig((prev) => ({ ...prev, ...updates }))}
      />

      {/* Error display */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mt-6 rounded-lg border border-[var(--color-budget-over)] bg-red-950 p-4 text-sm"
        >
          <p className="font-semibold text-[var(--color-budget-over)]">Build failed</p>
          <p className="mt-1 text-[var(--color-text-secondary)]">{error.message}</p>
          <button
            type="button"
            onClick={reset}
            className="mt-2 text-xs text-[var(--color-accent)] hover:underline focus:outline-none"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Build button */}
      <div className="mt-8 space-y-4">
        <button
          type="button"
          onClick={handleBuild}
          disabled={!commander || isBuilding}
          aria-busy={isBuilding}
          className={[
            'w-full rounded-lg px-6 py-4 text-base font-semibold transition-all',
            'bg-[var(--color-accent)] text-white',
            'hover:bg-[var(--color-accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
            'disabled:opacity-40 disabled:cursor-not-allowed',
          ].join(' ')}
        >
          {isBuilding ? (
            <span className="flex items-center justify-center gap-3">
              <svg
                className="h-5 w-5 animate-spin"
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
              Building deck...
            </span>
          ) : (
            `Build Deck${commander ? ` with ${commander.name}` : ''}`
          )}
        </button>

        {/* Progress message */}
        {isBuilding && (
          <p
            role="status"
            aria-live="polite"
            className="text-center text-sm text-[var(--color-text-secondary)] animate-pulse"
          >
            {BUILD_MESSAGES[messageIndex]}
          </p>
        )}

        {!commander && (
          <p className="text-center text-sm text-[var(--color-text-secondary)]">
            Select a commander above to enable building.
          </p>
        )}
      </div>
    </div>
  );
}

import { useEffect } from 'react';
import { useNavigate, Link } from 'react-router';
import { useDeckList, useDeleteDeck } from '../hooks/useDeck';
import CommanderSearch from '../components/search/CommanderSearch';
import type { CardResponse, DeckListItem } from '../api/types';
import { formatPrice, formatDate } from '../utils/format';

/**
 * Landing page with commander search CTA and recent decks list.
 * Includes deck stats (price, card count), delete buttons, and empty state.
 */
export default function HomePage() {
  useEffect(() => {
    document.title = 'MTG Deck Maker';
  }, []);

  const navigate = useNavigate();
  const { decks, isLoading: decksLoading } = useDeckList();
  const { deleteDeck, isDeleting } = useDeleteDeck();

  const handleCommanderSelect = (card: CardResponse) => {
    navigate('/build', { state: { commander: card } });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-12">
      {/* Hero */}
      <section className="py-10 text-center">
        <h1 className="text-4xl font-bold text-[var(--color-text-primary)] sm:text-5xl">
          MTG Commander
          <br />
          <span className="text-[var(--color-accent)]">Deck Builder</span>
        </h1>
        <p className="mt-4 text-lg text-[var(--color-text-secondary)]">
          Build optimized Commander decks with AI-assisted card selection.
        </p>
      </section>

      {/* Commander search CTA */}
      <section aria-labelledby="search-heading">
        <h2
          id="search-heading"
          className="mb-3 text-lg font-semibold text-[var(--color-text-primary)]"
        >
          Find a Commander
        </h2>
        <CommanderSearch
          onSelect={handleCommanderSelect}
          placeholder="Search for a commander to start building..."
        />
        <p className="mt-2 text-center text-sm text-[var(--color-text-secondary)]">
          Or{' '}
          <Link
            to="/build"
            className="text-[var(--color-accent)] underline hover:no-underline"
          >
            go to the Build page
          </Link>{' '}
          for full options.
        </p>
      </section>

      {/* Recent decks */}
      <section aria-labelledby="recent-heading">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2
              id="recent-heading"
              className="text-lg font-semibold text-[var(--color-text-primary)]"
            >
              Recent Decks
            </h2>
            {/* Deck count badge */}
            {!decksLoading && decks.length > 0 && (
              <span
                className="inline-flex items-center justify-center rounded-full bg-[var(--color-accent)] px-2 py-0.5 text-xs font-bold text-white"
                aria-label={`${decks.length} decks`}
              >
                {decks.length}
              </span>
            )}
          </div>
          <Link
            to="/build"
            className="text-sm text-[var(--color-accent)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] rounded"
          >
            Build new deck
          </Link>
        </div>

        {decksLoading ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading decks">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]"
              />
            ))}
          </div>
        ) : decks.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="space-y-2" role="list">
            {decks.map((deck) => (
              <DeckListRow
                key={deck.id}
                deck={deck}
                onDelete={() => deleteDeck(deck.id)}
                isDeleting={isDeleting}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] px-6 py-14 text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--color-surface-raised)]">
        <svg
          className="h-8 w-8 text-[var(--color-text-secondary)]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M12 8v8M8 12h8" />
        </svg>
      </div>
      <p className="font-medium text-[var(--color-text-primary)]">No decks yet</p>
      <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
        Build your first Commander deck to get started.
      </p>
      <Link
        to="/build"
        className={[
          'mt-4 inline-block rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-white',
          'hover:bg-[var(--color-accent-hover)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
        ].join(' ')}
      >
        Build your first deck
      </Link>
    </div>
  );
}

interface DeckListRowProps {
  deck: DeckListItem;
  onDelete: () => void;
  isDeleting: boolean;
}

function DeckListRow({ deck, onDelete, isDeleting }: DeckListRowProps) {
  return (
    <li className="group relative flex items-center gap-2">
      {/* Main clickable row */}
      <Link
        to={`/deck/${deck.id}`}
        className={[
          'flex flex-1 items-center justify-between rounded-lg px-4 py-3',
          'border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
          'hover:bg-[var(--color-surface-raised)] transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
        ].join(' ')}
      >
        {/* Left: name + meta */}
        <div className="min-w-0">
          <p className="truncate font-medium text-[var(--color-text-primary)]">{deck.name}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-[var(--color-text-secondary)]">
            <span>{deck.total_cards} cards</span>
            <span aria-hidden="true">&bull;</span>
            <span className="capitalize">{deck.format}</span>
            <span aria-hidden="true">&bull;</span>
            <span>{formatDate(deck.created_at)}</span>
          </div>
        </div>

        {/* Right: price */}
        <div className="ml-4 shrink-0 text-right">
          <p className="font-mono text-sm font-semibold text-[var(--color-budget-ok)]">
            {formatPrice(deck.total_price)}
          </p>
          {deck.budget_target != null && (
            <p className="text-xs text-[var(--color-text-secondary)]">
              of {formatPrice(deck.budget_target)}
            </p>
          )}
        </div>
      </Link>

      {/* Delete button — appears on hover/focus */}
      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        aria-label={`Delete deck ${deck.name}`}
        className={[
          'shrink-0 rounded-lg border border-transparent p-2 text-[var(--color-text-secondary)]',
          'opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity',
          'hover:border-[var(--color-budget-over)] hover:text-[var(--color-budget-over)]',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-budget-over)]',
          'disabled:cursor-not-allowed disabled:opacity-30',
        ].join(' ')}
      >
        <svg
          className="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14H6L5 6" />
          <path d="M10 11v6M14 11v6" />
          <path d="M9 6V4h6v2" />
        </svg>
      </button>
    </li>
  );
}

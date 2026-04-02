import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { useDeck, useDeleteDeck } from '../hooks/useDeck';
import CommanderBanner from '../components/deck/CommanderBanner';
import DeckStats from '../components/deck/DeckStats';
import ManaCurveChart from '../components/deck/ManaCurveChart';
import ColorDistribution from '../components/deck/ColorDistribution';
import DeckCategoryGroup from '../components/deck/DeckCategoryGroup';
import ExportMenu from '../components/deck/ExportMenu';
import BuyAllMenu from '../components/deck/BuyAllMenu';
import AdvisePanel from '../components/deck/AdvisePanel';
import UpgradePanel from '../components/deck/UpgradePanel';
import StrategyGuidePanel from '../components/deck/StrategyGuide';
import CardLightbox from '../components/card/CardLightbox';
import { getCategorySortOrder } from '../utils/categories';
import type { DeckCardResponse } from '../api/types';

/**
 * Full deck detail view.
 *
 * Layout:
 *   - CommanderBanner (full-width hero)
 *   - DeckStats (4-cell grid)
 *   - Two-column: card list by category | sidebar charts
 */
export default function DeckViewPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const navigate = useNavigate();
  const id = deckId ? parseInt(deckId, 10) : null;
  const { deck, isLoading, error, refetch } = useDeck(id);
  const { deleteDeck, isDeleting } = useDeleteDeck();

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [lightboxCard, setLightboxCard] = useState<{ name: string; url: string } | null>(null);

  // Group non-commander cards by category, sorted by category order.
  // Must be declared before any early returns to satisfy Rules of Hooks.
  const categoryMap = useMemo(() => {
    const cards = deck?.cards ?? [];
    const nonCommanderCards = cards.filter((c) => !c.is_commander);
    return nonCommanderCards.reduce<Record<string, DeckCardResponse[]>>(
      (acc, card) => {
        const cat = card.category ?? 'utility';
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(card);
        return acc;
      },
      {}
    );
  }, [deck?.cards]);

  const sortedCategories = useMemo(
    () => Object.keys(categoryMap).sort((a, b) => getCategorySortOrder(a) - getCategorySortOrder(b)),
    [categoryMap]
  );

  const handleCardClick = useCallback((card: DeckCardResponse) => {
    if (card.image_url) {
      setLightboxCard({ name: card.card_name, url: card.image_url });
    }
  }, []);

  useEffect(() => {
    if (deck) {
      document.title = `${deck.name} | MTG Deck Maker`;
    } else {
      document.title = 'Deck | MTG Deck Maker';
    }
  }, [deck]);

  const handleDeleteClick = useCallback(() => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    if (id == null) return;
    deleteDeck(id, {
      onSuccess: () => navigate('/'),
    });
  }, [confirmDelete, id, deleteDeck, navigate]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6" aria-busy="true" aria-label="Loading deck">
        {/* Banner skeleton */}
        <div className="flex justify-center gap-6 py-8">
          <div className="flex flex-col items-center gap-3">
            <div className="h-72 w-48 rounded-lg bg-[var(--color-surface-raised)]" />
            <div className="h-5 w-36 rounded bg-[var(--color-surface-raised)]" />
            <div className="h-3 w-28 rounded bg-[var(--color-surface-raised)]" />
          </div>
        </div>
        {/* Stats skeleton */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-lg bg-[var(--color-surface-raised)]" />
          ))}
        </div>
        {/* Card list skeleton */}
        <div className="space-y-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-11 rounded-md bg-[var(--color-surface-alt)] border border-[var(--color-border)]" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16 text-center" role="alert">
        <p className="text-lg font-semibold text-[var(--color-budget-over)]">
          Error loading deck
        </p>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{error.message}</p>
        <div className="mt-4 flex justify-center gap-4">
          <button
            type="button"
            onClick={() => refetch()}
            className="text-sm text-[var(--color-accent)] hover:underline focus:outline-none"
          >
            Try again
          </button>
          <Link
            to="/"
            className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] underline"
          >
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  if (!deck) {
    return (
      <div className="py-16 text-center">
        <p className="text-[var(--color-text-secondary)]">Deck not found.</p>
        <Link
          to="/"
          className="mt-2 inline-block text-[var(--color-accent)] hover:underline"
        >
          Back to Home
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top navigation bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Breadcrumb" className="text-sm">
          <Link
            to="/"
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            Home
          </Link>
          <span className="mx-2 text-[var(--color-text-secondary)]" aria-hidden="true">/</span>
          <span className="text-[var(--color-text-primary)] truncate max-w-xs" title={deck.name}>
            {deck.name}
          </span>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {id != null && <ExportMenu deckId={id} />}
          <BuyAllMenu cards={deck.cards} />

          {/* Delete button */}
          <button
            type="button"
            onClick={handleDeleteClick}
            disabled={isDeleting}
            aria-label={confirmDelete ? 'Confirm delete deck' : 'Delete deck'}
            className={[
              'rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-budget-over)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              confirmDelete
                ? 'border-[var(--color-budget-over)] bg-red-950 text-[var(--color-budget-over)]'
                : 'border-[var(--color-border)] bg-[var(--color-surface-alt)] text-[var(--color-text-secondary)] hover:border-[var(--color-budget-over)] hover:text-[var(--color-budget-over)]',
            ].join(' ')}
          >
            {isDeleting ? 'Deleting...' : confirmDelete ? 'Confirm Delete' : 'Delete'}
          </button>

          {confirmDelete && !isDeleting && (
            <button
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] focus:outline-none"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Deck name */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">{deck.name}</h1>
        <p className="mt-0.5 text-sm capitalize text-[var(--color-text-secondary)]">{deck.format}</p>
      </div>

      {/* Commander banner */}
      <CommanderBanner commanders={deck.commanders} />

      {/* Stats grid */}
      <DeckStats
        totalCards={deck.total_cards}
        totalPrice={deck.total_price}
        averageCmc={deck.average_cmc}
        budgetTarget={deck.budget_target}
        format={deck.format}
      />

      {/* Main two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
        {/* Left: Card list by category */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
            Cards ({deck.total_cards})
          </h2>

          {sortedCategories.map((category) => (
            <DeckCategoryGroup
              key={category}
              category={category}
              cards={categoryMap[category]}
              budget={deck.budget_target ?? undefined}
              defaultExpanded={true}
              onCardClick={handleCardClick}
            />
          ))}
        </div>

        {/* Right: Charts sidebar */}
        <aside className="space-y-4" aria-label="Deck analytics">
          <ManaCurveChart cards={deck.cards} />
          {Object.keys(deck.color_distribution).length > 0 && (
            <ColorDistribution colorDistribution={deck.color_distribution} />
          )}
        </aside>
      </div>

      {/* Strategy Guide */}
      {id != null && (
        <StrategyGuidePanel deckId={id} cards={deck.cards} />
      )}

      {/* Upgrade Recommendations */}
      {id != null && (
        <UpgradePanel deckId={id} />
      )}

      {/* AI Advisor */}
      {id != null && (
        <AdvisePanel deckId={id} />
      )}

      {/* Card image lightbox */}
      {lightboxCard && (
        <CardLightbox
          imageUrl={lightboxCard.url}
          cardName={lightboxCard.name}
          onClose={() => setLightboxCard(null)}
        />
      )}

      {/* Footer link */}
      <div className="border-t border-[var(--color-border)] pt-4">
        <Link
          to="/"
          className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors underline"
        >
          Back to Home
        </Link>
      </div>
    </div>
  );
}

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ResearchResponse } from '../../api/types';

interface ResearchResultDisplayProps {
  result: ResearchResponse;
}

/**
 * Displays a structured ResearchResponse from the LLM advisor.
 * Handles parse_success=false gracefully by showing raw response.
 * Each section is independently collapsible.
 *
 * Usage:
 *   <ResearchResultDisplay result={researchData} />
 */
export default function ResearchResultDisplay({ result }: ResearchResultDisplayProps) {
  return (
    <div className="space-y-4" aria-label={`Research results for ${result.commander_name}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-[var(--color-text-primary)]">
          {result.commander_name}
        </h2>
        {!result.parse_success && (
          <span
            className="rounded border border-[var(--color-budget-warn)] px-2 py-0.5 text-xs text-[var(--color-budget-warn)]"
            role="status"
            aria-label="Partial parse results"
          >
            Partial results
          </span>
        )}
      </div>

      {/* Strategy Overview — always shown as markdown prose */}
      {result.strategy_overview && (
        <CollapsibleSection title="Strategy Overview" defaultOpen>
          <div className="prose-sm max-w-none text-[var(--color-text-primary)] leading-relaxed [&_p]:mb-2 [&_strong]:text-[var(--color-text-primary)] [&_em]:text-[var(--color-text-secondary)]">
            <ReactMarkdown>{result.strategy_overview}</ReactMarkdown>
          </div>
        </CollapsibleSection>
      )}

      {/* Key Cards — wide grid */}
      {result.key_cards.length > 0 && (
        <CollapsibleSection title={`Key Cards (${result.key_cards.length})`} defaultOpen>
          <CardChipGrid items={result.key_cards} variant="default" />
        </CollapsibleSection>
      )}

      {/* Two-column row: Budget Staples + Combos */}
      <div className="grid gap-4 sm:grid-cols-2">
        {result.budget_staples.length > 0 && (
          <CollapsibleSection title="Budget Staples" defaultOpen>
            <BulletList items={result.budget_staples} variant="success" />
          </CollapsibleSection>
        )}

        {result.combos.length > 0 && (
          <CollapsibleSection title="Notable Combos" defaultOpen>
            <BulletList items={result.combos} variant="default" />
          </CollapsibleSection>
        )}
      </div>

      {/* Two-column row: Win Conditions + Cards to Avoid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {result.win_conditions.length > 0 && (
          <CollapsibleSection title="Win Conditions" defaultOpen>
            <BulletList items={result.win_conditions} variant="default" />
          </CollapsibleSection>
        )}

        {result.cards_to_avoid.length > 0 && (
          <CollapsibleSection title="Cards to Avoid" defaultOpen>
            <BulletList items={result.cards_to_avoid} variant="danger" />
          </CollapsibleSection>
        )}
      </div>

      {/* Raw response fallback when parse failed and all fields are empty */}
      {!result.parse_success && allFieldsEmpty(result) && (
        <CollapsibleSection title="Raw AI Response" defaultOpen>
          <div className="rounded-md bg-[var(--color-surface)] p-3 text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap font-mono">
            {result.strategy_overview || 'No response content available.'}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function allFieldsEmpty(result: ResearchResponse): boolean {
  return (
    result.key_cards.length === 0 &&
    result.budget_staples.length === 0 &&
    result.combos.length === 0 &&
    result.win_conditions.length === 0 &&
    result.cards_to_avoid.length === 0
  );
}

// ---------------------------------------------------------------------------
// CollapsibleSection
// ---------------------------------------------------------------------------

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function CollapsibleSection({ title, defaultOpen = true, children }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className={[
          'flex w-full items-center justify-between px-4 py-3',
          'text-left transition-colors',
          'hover:bg-[var(--color-surface-raised)] rounded-lg',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
        ].join(' ')}
      >
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
          {title}
        </h3>
        <ChevronIcon isOpen={isOpen} />
      </button>

      {isOpen && (
        <div className="px-4 pb-4">
          {children}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// CardChipGrid — displays card names as pill chips in a wrapping grid
// ---------------------------------------------------------------------------

interface CardChipGridProps {
  items: string[];
  variant: 'default' | 'success' | 'danger';
}

function CardChipGrid({ items, variant }: CardChipGridProps) {
  const colorClass =
    variant === 'danger'
      ? 'text-[var(--color-budget-over)] border-red-900 bg-red-950/40'
      : variant === 'success'
      ? 'text-[var(--color-budget-ok)] border-green-900 bg-green-950/40'
      : 'text-[var(--color-text-primary)] border-[var(--color-border)] bg-[var(--color-surface-raised)]';

  return (
    <ul className="flex flex-wrap gap-2" aria-label="Card list">
      {items.map((card, i) => (
        <li
          key={i}
          className={[
            'rounded-md border px-2.5 py-1 text-xs font-medium',
            colorClass,
          ].join(' ')}
        >
          {card}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// BulletList — simple vertical list with colored bullets
// ---------------------------------------------------------------------------

interface BulletListProps {
  items: string[];
  variant: 'default' | 'success' | 'danger';
}

function BulletList({ items, variant }: BulletListProps) {
  const textClass =
    variant === 'danger'
      ? 'text-[var(--color-budget-over)]'
      : variant === 'success'
      ? 'text-[var(--color-budget-ok)]'
      : 'text-[var(--color-text-primary)]';

  const bulletClass =
    variant === 'danger'
      ? 'text-[var(--color-budget-over)]'
      : variant === 'success'
      ? 'text-[var(--color-budget-ok)]'
      : 'text-[var(--color-accent)]';

  return (
    <ul className="space-y-1.5" aria-label="List">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm">
          <span className={['mt-1 text-xs leading-none', bulletClass].join(' ')} aria-hidden="true">
            &#x25CF;
          </span>
          <span className={textClass}>{item}</span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// ChevronIcon
// ---------------------------------------------------------------------------

function ChevronIcon({ isOpen }: { isOpen: boolean }) {
  return (
    <svg
      className={[
        'h-4 w-4 text-[var(--color-text-secondary)] transition-transform duration-200',
        isOpen ? 'rotate-180' : 'rotate-0',
      ].join(' ')}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

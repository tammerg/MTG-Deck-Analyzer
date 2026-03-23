import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useStrategyGuide } from '../../hooks/useStrategyGuide';
import type { GamePhaseResponse, HandSimulationResponse, KeySynergyResponse, WinPathResponse } from '../../api/types';

interface StrategyGuideProps {
  deckId: number;
}

export default function StrategyGuide({ deckId }: StrategyGuideProps) {
  const { generate, data, isPending, error } = useStrategyGuide(deckId);

  return (
    <section
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]"
      aria-label="Strategy Guide"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
            <BookIcon />
            Strategy Guide
          </h2>
          <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
            Win conditions, game plan, and opening hand analysis.
          </p>
        </div>
        <button
          type="button"
          onClick={() => generate()}
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
          {isPending ? 'Generating...' : data ? 'Regenerate' : 'Generate'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="mx-4 mt-3 rounded-md border border-[var(--color-budget-over)] bg-red-950/40 p-3 text-sm text-[var(--color-budget-over)]"
        >
          <strong className="block font-semibold">Error</strong>
          {error.message}
        </div>
      )}

      {/* Loading skeleton */}
      {isPending && !data && (
        <div className="space-y-3 p-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-[var(--color-surface-raised)]" />
          ))}
        </div>
      )}

      {/* Content */}
      {data && (
        <div className="space-y-4 p-4">
          {/* Archetype + Themes badge */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[var(--color-accent)]/20 px-3 py-1 text-xs font-semibold text-[var(--color-accent)] capitalize">
              {data.archetype}
            </span>
            {data.themes.map((theme) => (
              <span
                key={theme}
                className="rounded-full border border-[var(--color-border)] px-2.5 py-0.5 text-xs text-[var(--color-text-secondary)]"
              >
                {theme}
              </span>
            ))}
          </div>

          {/* Win Conditions */}
          {data.win_paths.length > 0 && <WinConditions winPaths={data.win_paths} />}

          {/* Game Plan Timeline */}
          {data.game_phases.length > 0 && <GamePlanTimeline phases={data.game_phases} />}

          {/* Opening Hand Simulator */}
          {data.hand_simulation && <OpeningHandStats simulation={data.hand_simulation} />}

          {/* Key Synergies */}
          {data.key_synergies.length > 0 && <KeySynergies synergies={data.key_synergies} />}

          {/* LLM Narrative */}
          <NarrativeSection narrative={data.llm_narrative} />
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Win Conditions
// ---------------------------------------------------------------------------

function WinConditions({ winPaths }: { winPaths: WinPathResponse[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Win Conditions ({winPaths.length})
      </h3>
      <div className="space-y-1">
        {winPaths.map((wp, i) => {
          const key = `${wp.name}-${i}`;
          const isOpen = expanded === key;
          return (
            <div key={key} className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
              <button
                type="button"
                onClick={() => setExpanded(isOpen ? null : key)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
                aria-expanded={isOpen}
              >
                <span className="flex items-center gap-2">
                  <span className="font-medium text-[var(--color-text-primary)]">{wp.name}</span>
                  {wp.combo_id && (
                    <span className="rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-amber-400">
                      COMBO
                    </span>
                  )}
                </span>
                <ChevronIcon open={isOpen} />
              </button>
              {isOpen && (
                <div className="border-t border-[var(--color-border)] px-3 py-2 text-sm">
                  <p className="text-[var(--color-text-secondary)]">{wp.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {wp.cards.map((card) => (
                      <span
                        key={card}
                        className="rounded bg-[var(--color-surface-raised)] px-2 py-0.5 text-xs text-[var(--color-text-primary)]"
                      >
                        {card}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Game Plan Timeline
// ---------------------------------------------------------------------------

function GamePlanTimeline({ phases }: { phases: GamePhaseResponse[] }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Game Plan
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {phases.map((phase) => (
          <div
            key={phase.phase_name}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
          >
            <div className="mb-1.5">
              <span className="text-sm font-semibold text-[var(--color-text-primary)]">{phase.phase_name}</span>
              <span className="ml-2 text-xs text-[var(--color-text-secondary)]">{phase.turn_range}</span>
            </div>
            <p className="mb-2 text-xs text-[var(--color-text-secondary)]">{phase.description}</p>
            <ul className="mb-2 space-y-0.5">
              {phase.priorities.map((p) => (
                <li key={p} className="text-xs text-[var(--color-text-primary)]">
                  &bull; {p}
                </li>
              ))}
            </ul>
            {phase.key_cards.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {phase.key_cards.slice(0, 5).map((card) => (
                  <span
                    key={card}
                    className="rounded bg-[var(--color-surface-raised)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
                  >
                    {card}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Opening Hand Stats
// ---------------------------------------------------------------------------

function OpeningHandStats({ simulation }: { simulation: HandSimulationResponse }) {
  const keepPct = Math.round(simulation.keep_rate * 100);
  const keepColor =
    keepPct >= 70
      ? 'text-[var(--color-budget-under)]'
      : keepPct >= 50
        ? 'text-amber-400'
        : 'text-[var(--color-budget-over)]';

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Opening Hand Analysis ({simulation.total_simulations} simulations)
      </h3>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
        {/* Stats row */}
        <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <div className={`text-lg font-bold ${keepColor}`}>{keepPct}%</div>
            <div className="text-xs text-[var(--color-text-secondary)]">Keep Rate</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[var(--color-text-primary)]">{simulation.avg_land_count}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">Avg Lands</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[var(--color-text-primary)]">{simulation.avg_ramp_count}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">Avg Ramp</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[var(--color-text-primary)]">{simulation.avg_cmc_in_hand}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">Avg CMC</div>
          </div>
        </div>

        {/* Mulligan advice */}
        <p className="mb-3 rounded bg-[var(--color-surface-raised)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
          {simulation.mulligan_advice}
        </p>

        {/* Sample hands */}
        {simulation.sample_hands.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs font-medium text-[var(--color-text-secondary)]">Sample Hands</div>
            {simulation.sample_hands.map((hand, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded border border-[var(--color-border)] px-2 py-1.5 text-xs"
              >
                <span
                  className={[
                    'rounded px-1.5 py-0.5 text-[10px] font-semibold',
                    hand.keep_recommendation
                      ? 'bg-emerald-900/40 text-emerald-400'
                      : 'bg-red-900/40 text-red-400',
                  ].join(' ')}
                >
                  {hand.keep_recommendation ? 'KEEP' : 'MULL'}
                </span>
                <span className="flex-1 truncate text-[var(--color-text-primary)]">
                  {hand.cards.join(', ')}
                </span>
                <span className="shrink-0 text-[var(--color-text-secondary)]">
                  {hand.land_count}L / {hand.ramp_count}R
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Key Synergies
// ---------------------------------------------------------------------------

function KeySynergies({ synergies }: { synergies: KeySynergyResponse[] }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Key Synergies ({synergies.length})
      </h3>
      <div className="space-y-1">
        {synergies.map((syn, i) => (
          <div
            key={i}
            className="flex items-start gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
          >
            <div className="flex shrink-0 items-center gap-1">
              <span className="rounded bg-[var(--color-surface-raised)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-primary)]">
                {syn.card_a}
              </span>
              <span className="text-xs text-[var(--color-text-secondary)]">+</span>
              <span className="rounded bg-[var(--color-surface-raised)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-primary)]">
                {syn.card_b}
              </span>
            </div>
            <span className="text-xs text-[var(--color-text-secondary)]">{syn.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LLM Narrative
// ---------------------------------------------------------------------------

function NarrativeSection({ narrative }: { narrative: string | null }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        AI Strategy Narrative
      </h3>
      {narrative ? (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 prose-sm max-w-none text-sm text-[var(--color-text-primary)] leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0">
          <ReactMarkdown>{narrative}</ReactMarkdown>
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-center text-xs text-[var(--color-text-secondary)]">
          Enable an LLM provider for narrative analysis.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function BookIcon() {
  return (
    <svg className="h-4 w-4 text-[var(--color-accent)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 text-[var(--color-text-secondary)] transition-transform ${open ? 'rotate-180' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

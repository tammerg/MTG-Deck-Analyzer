# MTG Deck Maker — Project Plan

## Project Overview

MTG Deck Maker is a CLI + Web API application that generates optimized Magic: The Gathering Commander decklists at various budget tiers. Given a commander and budget, it produces a complete 100-card deck using multi-factor scoring (synergy, power, price), archetype-adaptive category targets, mana curve shaping, combo awareness, and per-commander EDHREC data. It also provides deck analysis, upgrade recommendations, and LLM-powered advice via OpenAI or Anthropic.

**Current state:** Core engine complete through P1 algorithm improvements. Multi-provider LLM integration (Phase 2 + 2.5) fully implemented. Frontend scaffolded. 870 tests passing, zero failures. All work uncommitted.

## Architecture Reference

- **[ADR.md](./ADR.md)** — Architecture decisions, identified concerns (AC-1 through AC-7), and data source strategy
- **[ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md)** — Living spec for algorithm improvements (W1-W8 weakness catalog, priority matrix, measurement plan)
- **[FRONTEND_PLAN.md](./FRONTEND_PLAN.md)** — Complete frontend spec (React 19 + Vite + FastAPI, 5-phase implementation)

### Project Structure

```
src/mtg_deck_maker/
├── models/          card.py, deck.py, combo.py, edhrec_data.py
├── engine/          deck_builder.py, synergy.py, categories.py, budget_optimizer.py, power_level.py, mana_base.py
├── services/        build_service.py, advise_service.py, research_service.py, analyze_service.py, sync_service.py, upgrade_service.py
├── advisor/         llm_provider.py, anthropic_provider.py, openai_provider.py, retry.py, llm_advisor.py, analyzer.py
├── api/             commanderspellbook.py, edhrec.py
│   └── web/         FastAPI routers
├── db/              database.py, combo_repo.py, edhrec_repo.py, printing_repo.py, deck_repo.py
├── cli.py           Click CLI (build, analyze, upgrade, advise, research, validate, sync, search, config)
└── config.py        AppConfig (CLI > env > TOML > defaults)
```

---

## Current Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Foundation + schema + models + repos | Done |
| Phase 2 | Data seeding + Scryfall sync | Done |
| Phase 3 | CSV I/O (export, import, format detection) | Done |
| Phase 4 | Deck building engine (synergy, categories, budget optimizer, mana base) | Done |
| Phase 5 | Pricing engine (Scryfall prices, cheapest print selection) | Done |
| Phase 6 | Advisor + upgrade engine | Done |
| Phase 7 | LLM advisor (Claude integration) | Done |
| Phase 8 | CLI + polish (all commands wired) | Done |
| Phase 2 LLM | Multi-provider LLM (OpenAI + Anthropic abstraction, research command, --smart build) | Done |
| Phase 2.5 | Gap closure (CLI tests, model override, __init__ exports) | Done |
| P0 Algorithm | Tribal matching, archetype-adaptive targets, combo DB, per-commander EDHREC | Done |
| P1 Algorithm | Curve shaping, regex expansion (28 patterns), win conditions (20 patterns), redundancy awareness | Done |
| Frontend | React 19 + Vite scaffolded, FastAPI web routers | In Progress |

**Tests:** 765 passing, zero failures (1.87s full suite)

---

## Next Steps (Priority Order)

### Priority 0: Stabilize — DONE

- [x] Commit all uncommitted work (19 atomic commits pushed)
- [x] Remove dead code: legacy Anthropic path (`_get_advice_legacy()`), unused `_assign_card_prices()`
- [x] Delete stale plan files (PHASE2_IMPLEMENTATION.md, Phase2.5.md removed)
- [x] Consolidate and trim test suite (870 → 765 tests, 3500 lines removed)
- [x] Fix hanging sync tests (unmocked `fetch_combos()` making real HTTP calls)

### Priority 1: Performance Fixes — DONE

- [x] **AC-2: Bulk price loading** — Added `get_cheapest_prices()` batch query with chunked IN clause (900/chunk)
- [x] **AC-3: SQL-level color identity filtering** — Rewrote with NOT LIKE exclusion patterns in SQL
- [x] **AC-1: Extract build orchestration** — Added `BuildService.build_from_db()`, CLI and API are thin wrappers
- [ ] **AC-4: Fix SSE streaming** — In progress: queue bridge between sync thread and async SSE generator

### Priority 2: Code Quality — In Progress

- [ ] **AC-5: ScoredCandidate dataclass** — In progress: replacing untyped dicts with typed dataclass
- [ ] **AC-6: Standardize API clients** — In progress: migrating EDHREC/CommanderSpellbook from urllib to httpx
- [x] **AC-7: Remove dead code** — Done (part of P0 stabilization)

### Priority 3: Measurement Infrastructure

Build the tooling needed to validate algorithm changes. See [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md) for the full measurement plan.

- [ ] `DeckComparison` tool — Generate two decks with different algorithm versions, compare metrics side-by-side
- [ ] EDHREC overlap metric — % of selected cards appearing in EDHREC average decklist for that commander
- [ ] Category coverage score — % of minimum category targets met
- [ ] Mana curve smoothness metric — Standard deviation from ideal curve distribution
- [ ] Benchmark suite — 5-10 commanders with golden reference decklists for regression testing

### Priority 4: Algorithm Improvements (P2)

Open items from [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md):

- [ ] **W2c: Pairwise synergy** — Compute card-to-card synergy for top N candidates, detect "packages" of cards that work together
- [ ] **W7: Deck-internal synergy audit** — Post-build optimization pass: compute pairwise synergy for all 100 cards, swap low-synergy outliers
- [ ] **W1b: LLM-assisted categorization** — Batch uncategorized cards through LLM for JSON categorization, cache in DB
- [ ] **W4b: LLM-suggested category ratios** — Add `category_targets` to research JSON schema, let LLM recommend ratios per commander

### Priority 5: Frontend Implementation

See [FRONTEND_PLAN.md](./FRONTEND_PLAN.md) for the complete 5-phase spec:

1. Project setup (React 19 + Vite + TailwindCSS + React Router)
2. Core pages (commander search, deck builder, deck viewer)
3. Advanced features (budget slider, category editor, mana curve visualization)
4. LLM integration (research panel, smart build toggle, advice chat)
5. Polish (responsive design, loading states, error handling, accessibility)

### Priority 6: Algorithm Improvements (P3)

Long-term algorithm work from [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md):

- [ ] **W3b: Trained scoring model** — Train on EDHREC decklists. Features: card keywords, commander keywords, theme overlap, category. Target: inclusion rate.
- [ ] **W2d: LLM synergy matrix** — Use LLM to generate pairwise synergy scores for top 200 candidates per commander. Cache per commander.

---

## Constraints

- **Python 3.14**, dataclasses with `__slots__`
- **TDD** — all new code has tests first, all LLM calls mocked
- **Conventional commits** — `<type>(<scope>): <subject>`
- **Deck algorithm quality is the core value proposition** — every change evaluated against ALGORITHM_ROADMAP.md
- **Graceful degradation** — every external dependency has a fallback path (Tier 0-5 ladder)
- **No breaking changes** to CLI interface without major version bump
- **870 tests**, zero failures as baseline

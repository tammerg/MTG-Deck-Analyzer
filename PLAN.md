# MTG Deck Maker — Project Plan

## Project Overview

MTG Deck Maker is a CLI + Web API application that generates optimized Magic: The Gathering Commander decklists at various budget tiers. Given a commander and budget, it produces a complete 100-card deck using multi-factor scoring (synergy, power, price), archetype-adaptive category targets, mana curve shaping, combo awareness, and per-commander EDHREC data. It also provides deck analysis, upgrade recommendations, and LLM-powered advice via OpenAI or Anthropic.

**Current state:** Core engine complete through P4 algorithm improvements. LLM synergy matrix (W2d) and ML predictor (W3b partial) integrated into engine. Strategy Guide feature fully implemented. Multi-provider LLM integration (Phase 2 + 2.5) fully implemented. Frontend complete. 1129 Python tests + 58 frontend tests passing. All work committed.

## Architecture Reference

- **[ADR.md](./ADR.md)** — Architecture decisions, identified concerns (AC-1 through AC-7), and data source strategy
- **[ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md)** — Living spec for algorithm improvements (W1-W8 weakness catalog, priority matrix, measurement plan)
- **[FRONTEND_PLAN.md](./FRONTEND_PLAN.md)** — Complete frontend spec (React 19 + Vite + FastAPI, 5-phase implementation)

### Project Structure

```
src/mtg_deck_maker/
├── models/          card.py, deck.py, combo.py, edhrec_data.py, strategy_guide.py, scored_candidate.py, commander.py, printing.py
├── engine/          deck_builder.py, synergy.py, synergy_audit.py, categories.py, budget_optimizer.py, power_level.py, mana_base.py, strategy_guide.py
├── services/        build_service.py, advise_service.py, research_service.py, analyze_service.py, sync_service.py, upgrade_service.py, strategy_guide_service.py
├── advisor/         llm_provider.py, anthropic_provider.py, openai_provider.py, retry.py, llm_advisor.py, llm_categorizer.py, llm_synergy.py, analyzer.py, upgrade.py
├── ml/              features.py, trainer.py, predictor.py
├── metrics/         category_coverage.py, curve_smoothness.py, edhrec_overlap.py, budget_efficiency.py, synergy_density.py, comparison.py, benchmark.py
├── utils/           colors.py, formatting.py
├── api/             commanderspellbook.py, edhrec.py
│   └── web/         FastAPI routers + Pydantic schemas
├── db/              database.py, combo_repo.py, edhrec_repo.py, printing_repo.py, deck_repo.py, card_repo.py, price_repo.py, llm_synergy_repo.py
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
| Frontend | React 19 + Vite + all pages + FastAPI API layer | Done |

**Tests:** 1129 Python tests + 58 frontend tests passing, zero failures

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
- [x] **AC-4: Fix SSE streaming** — Queue bridge between sync thread and async SSE generator

### Priority 2: Code Quality — DONE

- [x] **AC-5: ScoredCandidate dataclass** — Replaced untyped dicts with `ScoredCandidate` dataclass with slots
- [x] **AC-6: Standardize API clients** — Migrated EDHREC client from urllib to httpx (CommanderSpellbook still urllib, lower priority)
- [x] **AC-7: Remove dead code** — Done (part of P0 stabilization)

### Priority 3: Measurement Infrastructure — DONE

Build the tooling needed to validate algorithm changes. See [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md) for the full measurement plan.

- [x] Category coverage score — `metrics/category_coverage.py` (14 tests)
- [x] Mana curve smoothness metric — `metrics/curve_smoothness.py` (17 tests)
- [x] EDHREC overlap metric — `metrics/edhrec_overlap.py` (18 tests)
- [x] Budget efficiency metric — `metrics/budget_efficiency.py` (19 tests)
- [x] `DeckComparison` tool — `metrics/comparison.py` (19 tests)
- [x] Benchmark suite — `metrics/benchmark.py`, 8 reference commanders with validation thresholds (21 tests)

### Priority 4: Algorithm Improvements (P2) — DONE

All items from [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md) P2 tier:

- [x] **W2c: Pairwise synergy** — `compute_pairwise_synergy()`, `compute_package_score()`, `find_synergy_packages()` in synergy.py (21 tests)
- [x] **W7: Deck-internal synergy audit** — `audit_synergy()` in synergy_audit.py: pairwise audit, outlier detection, swap suggestions (11 tests)
- [x] **W1b: LLM-assisted categorization** — `LLMCategorizer` in advisor/llm_categorizer.py: batched LLM categorization with validation (25 tests)
- [x] **W4b: LLM-suggested category ratios** — `category_targets` in ResearchResult, LLM prompt extended (13 tests)

### Priority 5: Frontend Implementation — DONE

See [FRONTEND_PLAN.md](./FRONTEND_PLAN.md) for the complete 5-phase spec:

- [x] Project setup (React 19 + Vite + TailwindCSS + React Router)
- [x] Core pages (HomePage, BuildPage, DeckViewPage, SearchPage, ResearchPage, SettingsPage)
- [x] Advanced features (budget slider, mana curve chart, color distribution, category groups)
- [x] LLM integration (research panel, smart build toggle, AdvisePanel)
- [x] Polish (responsive design, loading skeletons, error boundaries, accessibility/aria)
- [x] Backend API layer (FastAPI routers, Pydantic schemas, CORS middleware, SSE sync)
- [x] `mtg-deck serve` CLI command (uvicorn integration, --host/--port/--reload, 5 tests)
- [x] Frontend tests (vitest + testing-library, 58 tests across utils + components)
- [x] Code-splitting (lazy routes + vendor chunks, main bundle 192KB down from 514KB)

### Priority 6: Strategy Guide Feature — DONE

See [STRATEGY_GUIDE_PLAN.md](./STRATEGY_GUIDE_PLAN.md) for the full spec (all items implemented):

- [x] Models — `models/strategy_guide.py` (HandSample, HandSimulationResult, WinPath, GamePhase, KeySynergy, StrategyGuide)
- [x] Engine — `engine/strategy_guide.py` (opening hand simulation, win condition analysis, game phase planning, key synergy identification)
- [x] Service — `services/strategy_guide_service.py` (DB loading, LLM narrative enrichment with graceful degradation)
- [x] API — POST `/decks/{deck_id}/strategy-guide` endpoint with Pydantic schemas
- [x] Frontend — `StrategyGuide.tsx` component, `useStrategyGuide.ts` hook, mounted in DeckViewPage

### Priority 7: Algorithm Improvements (P3) — PARTIAL

Long-term algorithm work from [ALGORITHM_ROADMAP.md](./ALGORITHM_ROADMAP.md):

- [x] **W2d: LLM synergy matrix** — `advisor/llm_synergy.py` + `db/llm_synergy_repo.py`, integrated into budget optimizer via `_compute_llm_synergy_bonus()`
- [~] **W3b: Trained scoring model** — `ml/features.py`, `ml/trainer.py`, `ml/predictor.py` implemented; predictor integrated into `deck_builder.py`. Training pipeline present but requires numpy (optional dependency). Partially complete.

### Priority 8: ML Integration — IN PROGRESS

- [x] Feature engineering for card-commander pairs (`ml/features.py`)
- [x] Model training pipeline (`ml/trainer.py`)
- [x] Power predictor for card-commander scoring (`ml/predictor.py`)
- [x] Engine integration — ML predictions used in `deck_builder.py` card selection
- [ ] Model training on EDHREC data (requires numpy, not yet run at scale)

---

## Constraints

- **Python 3.14**, dataclasses with `__slots__`
- **TDD** — all new code has tests first, all LLM calls mocked
- **Conventional commits** — `<type>(<scope>): <subject>`
- **Deck algorithm quality is the core value proposition** — every change evaluated against ALGORITHM_ROADMAP.md
- **Graceful degradation** — every external dependency has a fallback path (Tier 0-5 ladder)
- **No breaking changes** to CLI interface without major version bump
- **1129 Python tests + 58 frontend tests**, zero failures as baseline

# Architecture Decision Record

## ADR-001: System Architecture

- **Status:** Accepted
- **Date:** 2026-03-20
- **Context:** MTG Deck Maker is a CLI + Web API application that generates optimized Magic: The Gathering Commander decklists at various budget tiers, provides upgrade recommendations, and offers LLM-powered advice.
- **Decision:** Layered architecture with strict dependency direction: `models → engine → services → CLI/API`. The engine layer contains pure algorithms (synergy scoring, categorization, budget optimization, mana base construction). Services orchestrate engine calls with data access. CLI and API are thin presentation layers.
- **Consequences:**
  - Clean separation of concerns — engine modules are independently testable with no I/O dependencies
  - Services can be shared between CLI and API without duplication (see AC-1 for current gap)
  - New presentation layers (web, Discord bot) can be added without touching engine code

### Module Map

```
src/mtg_deck_maker/
├── models/          # Card, Deck, Combo, EDHRECData dataclasses
├── engine/          # deck_builder, synergy, categories, budget_optimizer, power_level, mana_base
├── services/        # build_service, advise_service, research_service, analyze_service, sync_service, upgrade_service
├── advisor/         # llm_provider (ABC + factory), anthropic_provider, openai_provider, retry, llm_advisor, analyzer
├── api/             # commanderspellbook, edhrec (data source clients)
│   └── web/         # FastAPI routers (decks, sync, etc.)
├── db/              # database, combo_repo, edhrec_repo, printing_repo, deck_repo
├── cli.py           # Click CLI entry point
└── config.py        # AppConfig with precedence: CLI > env > TOML > defaults
```

---

## ADR-002: Database Strategy

- **Status:** Accepted
- **Context:** The application needs local storage for ~30,000+ Commander-legal cards, their printings, prices, combos, and EDHREC data. Must work offline and require zero infrastructure.
- **Decision:** SQLite with `check_same_thread=False`. Schema includes `cards`, `printings`, `prices`, `card_tags`, `combos`, `edhrec_data`, `decks`, and `deck_cards` tables. Per-request connections in FastAPI via dependency injection.
- **Consequences:**
  - Zero-infrastructure local storage, built into Python stdlib
  - Full SQL for complex queries (price joins, card filtering)
  - No connection pooling — acceptable for single-user CLI, but a scaling concern for the web API
  - **Risk:** Full table scans for color identity filtering (loads all cards into Python, filters in-memory). See AC-3.

---

## ADR-003: LLM Integration Pattern

- **Status:** Accepted
- **Context:** LLM features (commander research, deck advice, smart build) should be optional — the core deck builder must work without any API keys.
- **Decision:**
  - Provider abstraction via `LLMProvider` ABC with `chat()`, `is_available()`, `name` interface
  - Factory function `get_provider(preferred)` resolves "openai", "anthropic", or "auto" (tries OpenAI first)
  - Lazy imports for optional SDKs (`openai` is an optional dependency)
  - Shared retry logic with exponential backoff for 429/5xx errors
  - `LLMConfig` dataclass in `AppConfig` with TOML, env var, and CLI overrides
- **Consequences:**
  - All LLM features degrade gracefully — `--smart` falls back to normal build, `research` and `advise` print clear instructions when no key is configured
  - Adding new providers (Google Gemini, local Ollama) requires only implementing `LLMProvider`
  - **Dead code identified:** Legacy Anthropic path in `llm_advisor.py` (`_get_advice_legacy()`) is superseded by the provider abstraction. Scheduled for removal.

---

## ADR-004: Scoring Algorithm

- **Status:** Accepted
- **Context:** Card selection must balance synergy with the commander, card power/popularity, budget constraints, mana curve, and category coverage.
- **Decision:** Multi-factor scoring with budget-aware selection:

  ```
  Card Score = (synergy * power) / price_weight + combo_bonus + priority_bonus

  synergy    = keyword_overlap(0.25) + theme_match(0.35) + color_synergy(0.20) + tribal(0.20)
  power      = per_commander_edhrec_inclusion(0.60) + category_confidence(0.40)
               (falls back to global EDHREC rank when per-commander data unavailable)
  price_wt   = 1.0 + ln(price / 0.25)
  ```

  Budget optimizer runs a 4-phase selection process:
  1. Fill archetype-adaptive category targets (aggro, control, combo, midrange, spellslinger profiles)
  2. Apply mana curve shaping via per-archetype ideal curve profiles with CMC penalties
  3. Apply diminishing returns after category max and functional duplicate penalty (Jaccard similarity on oracle text)
  4. Swap expensive cards for cheaper alternatives when over budget

- **Consequences:**
  - Decks are customized per commander via archetype detection and per-commander EDHREC data
  - Algorithm currently at **Tier 4** on the graceful degradation ladder (see ALGORITHM_ROADMAP.md), partially reaching Tier 5 with ML predictor integration
  - Synergy now includes commander-to-card, card-to-card pairwise synergy (W2c), deck-internal synergy audit (W7), and LLM-generated synergy matrices (W2d)

---

## ADR-005: Identified Architectural Concerns

These are known issues tracked for resolution. See PLAN.md for prioritized fix schedule.

| ID | Concern | Severity | Details |
|----|---------|----------|---------|
| AC-1 | ~~CLI/API orchestration duplication~~ | ~~Medium~~ | **RESOLVED.** Extracted `BuildService.build_from_db()` — CLI and API are thin wrappers. |
| AC-2 | ~~N+1 query explosion in web API~~ | ~~High~~ | **RESOLVED.** Added `get_cheapest_prices()` batch query with chunked IN clause (900/chunk). |
| AC-3 | ~~Full table scan for color identity~~ | ~~High~~ | **RESOLVED.** SQL-level NOT LIKE exclusion filtering, no Python-side full scan. |
| AC-4 | ~~SSE streaming broken~~ | ~~Medium~~ | **RESOLVED.** Queue bridge between sync thread and async SSE generator streams events in real time. |
| AC-5 | ~~Untyped dict threading for scored candidates~~ | ~~Low~~ | **RESOLVED.** Introduced `ScoredCandidate` dataclass with slots, migrated engine and optimizer to attribute access. |
| AC-6 | ~~Mixed sync/async in API clients~~ | ~~Low~~ | **RESOLVED.** Migrated EDHREC client from `urllib.request` to `httpx`. CommanderSpellbook still uses urllib (lower priority). |
| AC-7 | ~~Dead code~~ | ~~Low~~ | **RESOLVED.** Removed legacy Anthropic path, unused `_assign_card_prices()`, stale imports. |

---

## ADR-006: Data Source Strategy

- **Status:** Accepted
- **Context:** Deck quality depends on comprehensive, up-to-date card data from multiple sources with different availability guarantees.
- **Decision:** Multi-source with graceful degradation tiers:

  | Source | Data Provided | Integration Status |
  |--------|--------------|-------------------|
  | Scryfall Bulk | Card data, oracle text, prices, printings, EDHREC global rank | Integrated (primary) |
  | EDHREC JSON API | Per-commander card inclusion rates | Integrated (lazy fetch + cache) |
  | CommanderSpellbook API | Verified 2-3 card combos | Integrated (API + fallback JSON) |
  | EDHREC Commander Pages | Theme breakdowns, combo lists | Not integrated |
  | MTGGoldfish | Price trends, format metagame | Not integrated |

- **Degradation tiers:**
  ```
  Tier 0: Random legal cards within color identity (no external data)
  Tier 1: Regex categorization + EDHREC global rank + budget optimizer (Scryfall only)
  Tier 2: + Combo DB + tribal matching + curve shaping + archetype profiles (+ CommanderSpellbook)
  Tier 3: + Per-commander inclusion rates (+ EDHREC per-commander)
  Tier 4: + LLM-guided categorization + synergy matrix + adaptive targets  ← CURRENT
  Tier 5: + Trained models from EDHREC data, user feedback loop  ← PARTIALLY REACHED
  ```

- **Consequences:**
  - System always works at Tier 1 even if all optional data sources are unavailable
  - Each tier is independently testable
  - New data sources can be added without modifying the core engine

# Deck Strategy Guide Feature

> **COMPLETED** -- All items implemented (2026-03-23). Models, engine, service, API endpoint, frontend component, hooks, and tests are all in place.

Post-build analysis that explains win conditions, simulates opening hands (Monte Carlo), and outlines the game plan by phase. Algorithmic base always works; LLM narrative enrichment when API keys are available.

## New Files

### 1. `src/mtg_deck_maker/models/strategy_guide.py`
Dataclasses (`slots=True`) matching project conventions:

- **`HandSample`** — single simulated hand: `cards: list[str]`, `land_count`, `ramp_count`, `avg_cmc`, `has_win_enabler`, `keep_recommendation: bool`, `reason: str`
- **`HandSimulationResult`** — aggregate: `total_simulations`, `keep_rate`, `avg_land_count`, `avg_ramp_count`, `avg_cmc_in_hand`, `sample_hands: list[HandSample]` (5 representative), `mulligan_advice: str`
- **`WinPath`** — a win condition path: `name` (e.g. "Infinite Damage Combo"), `cards: list[str]`, `description`, `combo_id: str | None`
- **`GamePhase`** — phase guidance: `phase_name`, `turn_range`, `priorities: list[str]`, `key_cards: list[str]`, `description`
- **`KeySynergy`** — card pair: `card_a`, `card_b`, `reason`
- **`StrategyGuide`** — top-level container: `archetype`, `themes`, `win_paths`, `game_phases`, `hand_simulation`, `key_synergies`, `llm_narrative: str | None`

### 2. `src/mtg_deck_maker/engine/strategy_guide.py`
Pure algorithmic engine, no LLM dependency. Uses existing engine utilities.

#### `simulate_opening_hands(deck_cards, num_simulations=1000, seed=42) -> HandSimulationResult`
- Build flat 99-card list (exclude commander), shuffle & draw 7 per sim
- Score each hand (0-10):
  - Land count: 0-1 lands = 2, 6-7 lands = 2, 2 lands = 5, 3-4 lands = 8
  - Ramp bonus: +1 if any ramp card present
  - Curve penalty: -1 if avg CMC of non-lands > 4.0
  - Win enabler bonus: +1 if win_condition or tutor present
- Keep threshold: score >= 5
- Pick 5 sample hands: best, worst, median, borderline keep, borderline mulligan

#### `analyze_win_conditions(deck_cards, card_lookup, combos, archetype, commander_name) -> list[WinPath]`
- Filter cards with `category == "win_condition"`
- Group by sub-type using oracle_text regex: Direct Win, Drain/Life Loss, Combat/Commander Damage, Infinite Combo, Mill, Infect/Poison, Extra Combat
- For each `Combo` where ALL cards are in the deck, create a WinPath with combo result + description
- Sort: complete combos first, then by card count

#### `plan_game_phases(deck_cards, card_lookup, archetype, themes, avg_cmc) -> list[GamePhase]`
Three phases with archetype-aware priorities:
- **Early Game (Turns 1-3)**: ramp, mana fixing, low-CMC card draw. Key cards: `cmc <= 2` ramp/draw
- **Mid Game (Turns 4-7)**: establish board, deploy key pieces. Key cards: `3 <= cmc <= 5` in removal/win_condition/card_draw. Combo: find tutors. Control: prioritize interaction
- **Late Game (Turns 8+)**: execute win conditions, protect board. Key cards: high-CMC, win conditions, protection/counterspells

#### `identify_key_synergies(deck_cards, card_lookup, combos, max_results=10) -> list[KeySynergy]`
- Use `compute_pairwise_synergy()` from `engine/synergy.py` on deck's non-land cards
- Sort by score descending, take top N
- Generate reason string from shared themes/keywords/tribal/enabler-payoff

#### `generate_strategy_guide(deck, card_lookup, combos, archetype=None, seed=42, num_sims=1000) -> StrategyGuide`
- Orchestrator: calls all sub-functions above
- Uses `detect_archetype()` and `extract_themes()` from `engine/synergy.py` if archetype not provided
- Returns complete `StrategyGuide`

### 3. `src/mtg_deck_maker/services/strategy_guide_service.py`
Service layer following `analyze_service.py` pattern:

```python
class StrategyGuideService:
    def generate(self, deck_id: int, db: Database, llm_provider=None, seed=42, num_sims=1000) -> StrategyGuide:
```
- Load deck from `DeckRepository`
- Resolve full `Card` objects from `CardRepository` → build `dict[str, Card]` lookup
- Identify commander card
- Fetch combos from `ComboRepository.get_combos_for_cards(card_names)`
- Call `generate_strategy_guide()` from engine
- If `llm_provider` available: build context string (archetype, themes, win paths, phases), ask LLM for 2-3 paragraph narrative → attach as `llm_narrative`
- Catch LLM exceptions gracefully → return guide with `llm_narrative=None`

### 4. API Endpoint

**Modify:** `src/mtg_deck_maker/api/web/schemas/deck.py` — add Pydantic models:
- `StrategyGuideRequest(BaseModel)`: `provider: str = "auto"`, `num_simulations: int = 1000`, `seed: int = 42`
- `HandSampleResponse`, `HandSimulationResponse`, `WinPathResponse`, `GamePhaseResponse`, `KeySynergyResponse`, `StrategyGuideResponse` — mirror the dataclasses

**Modify:** `src/mtg_deck_maker/api/web/routers/decks.py` — add route:
```python
@router.post("/decks/{deck_id}/strategy-guide")
def strategy_guide(deck_id: int, req: StrategyGuideRequest, db=Depends(get_db)) -> StrategyGuideResponse:
```

### 5. Frontend

**Modify:** `frontend/src/api/types.ts` — add TS interfaces matching response schemas

**Modify:** `frontend/src/api/decks.ts` — add `getStrategyGuide(deckId, request?)` API function

**New:** `frontend/src/hooks/useStrategyGuide.ts` — `useMutation` pattern (like AdvisePanel), on-demand generation via button click

**New:** `frontend/src/components/deck/StrategyGuide.tsx` — collapsible section with sub-panels:
1. **Header**: "Strategy Guide" + "Generate" button
2. **Win Conditions**: accordion list of WinPaths — name, card badges, description
3. **Game Plan Timeline**: 3-column layout (Early/Mid/Late) — priorities list + key card badges
4. **Opening Hand Simulator**: keep rate % indicator, avg lands/ramp stats, 5 sample hand rows with keep/mulligan badge, mulligan advice text
5. **Key Synergies**: card pair list with reason
6. **LLM Narrative**: rendered via ReactMarkdown if present, otherwise "Enable an LLM provider for narrative analysis"

**Modify:** `frontend/src/pages/DeckViewPage.tsx` — add `<StrategyGuide deckId={id} />` between the card list section and `<AdvisePanel>`

## Files to Modify (Summary)

| File | Action |
|------|--------|
| `src/mtg_deck_maker/models/strategy_guide.py` | Create — dataclasses |
| `src/mtg_deck_maker/engine/strategy_guide.py` | Create — algorithmic engine |
| `src/mtg_deck_maker/services/strategy_guide_service.py` | Create — service layer |
| `src/mtg_deck_maker/api/web/schemas/deck.py` | Modify — add Pydantic schemas |
| `src/mtg_deck_maker/api/web/routers/decks.py` | Modify — add POST endpoint |
| `frontend/src/api/types.ts` | Modify — add TS interfaces |
| `frontend/src/api/decks.ts` | Modify — add API function |
| `frontend/src/hooks/useStrategyGuide.ts` | Create — useMutation hook |
| `frontend/src/components/deck/StrategyGuide.tsx` | Create — UI component |
| `frontend/src/pages/DeckViewPage.tsx` | Modify — mount component |
| `tests/test_engine/test_strategy_guide.py` | Create — engine tests |
| `tests/test_services/test_strategy_guide_service.py` | Create — service tests |
| `frontend/src/components/deck/__tests__/StrategyGuide.test.tsx` | Create — component tests |

## Testing Strategy

### Backend Engine (~30 tests)
- `TestSimulateOpeningHands`: all-land deck → low keep rate, all-spells → low keep rate, balanced → >0.6 keep rate, deterministic with seed, edge case 7-card deck, `_score_hand` unit tests
- `TestAnalyzeWinConditions`: "you win the game" → Direct Win path, complete combo → combo WinPath, partial combo excluded, infect grouped correctly, empty for utility-only deck
- `TestPlanGamePhases`: always 3 phases, archetype-specific priorities, key cards filtered by CMC
- `TestIdentifyKeySynergies`: respects max_results, empty input → empty output
- `TestGenerateStrategyGuide`: integration test, all fields populated, works without combos

### Backend Service (~5 tests)
- Service loads deck, resolves cards, calls engine
- LLM enrichment called when provider available (mock LLM)
- Graceful degradation when LLM fails
- Deck not found → error

### Frontend Component (~8 tests)
- Renders Generate button initially
- Loading state during mutation
- Displays all sections after data loads
- LLM narrative with ReactMarkdown when present
- Fallback message when no LLM narrative
- Error handling

## Implementation Order
1. Models (no dependencies)
2. Engine + engine tests (depends on existing synergy/categories)
3. Service + service tests (depends on engine + DB repos)
4. API schemas + route (depends on service)
5. Frontend types + API function + hook + component + tests
6. Integration into DeckViewPage

Steps 1-4 (backend) and step 5 (frontend types/hook) can be parallelized.

## Key Reuse Points
- `engine/synergy.py`: `detect_archetype()`, `extract_themes()`, `compute_pairwise_synergy()`
- `engine/categories.py`: category constants + `_WIN_CONDITION_PATTERNS`
- `db/combo_repo.py`: `get_combos_for_cards()`
- `advisor/analyzer.py`: `DeckAnalysis` pattern for structuring results
- `AdvisePanel.tsx`: `useMutation` + ReactMarkdown pattern for frontend

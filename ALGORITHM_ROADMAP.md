# Deck Algorithm Improvement Roadmap

> This is a living document. Every feature and refactor should be evaluated against these improvement vectors. **Deck quality is the product's core value proposition.**

## Current Algorithm Summary

```
Card Selection Score = (synergy * power) / price_weight

synergy  = keyword_overlap(0.25) + theme_match(0.35) + color_synergy(0.20) + tribal(0.20)
power    = per_commander_edhrec_inclusion(0.60) + category_confidence(0.40)
           (falls back to global edhrec_rank when per-commander data unavailable)
price_wt = 1.0 + ln(price / 0.25)
```

Post-scoring: budget optimizer fills archetype-adaptive category targets, applies mana curve shaping (per-archetype ideal curve profiles), diminishing returns after category max, and functional duplicate penalty (Jaccard similarity). Swaps expensive cards for cheaper ones when over budget. Mana base is built separately.

## Known Weaknesses

### W1: Regex-Only Categorization

**File:** `engine/categories.py`

The entire categorization engine is regex patterns against oracle text. This causes:

- **False negatives**: Cards with unusual wording get missed. "Look at the top N cards of your library, put one into your hand" is card draw but doesn't match "draw a card".
- **False positives**: "Counter target spell" in reminder text (stripped, but edge cases exist). Cards that reference counters (the game object) matched by counter (the spell action).
- **Missing categories**: No stax/hatebear category, no "finisher" vs "enabler" distinction, no "combo piece" category.
- **Modal cards**: MDFCs and modal spells may only be relevant on one face/mode.

**Improvement path:**
1. **Short-term**: Expand regex patterns to cover common misses (treasure/food/clue as ramp, impulsive draw, conditional card advantage)
2. **Medium-term**: Add a secondary classification pass using card keywords array from Scryfall (more reliable than oracle text parsing)
3. **Long-term**: LLM-assisted bulk categorization — batch 50 cards at a time, ask for JSON categorization, cache results in DB. Run once per sync, not per build.

### W2: Shallow Synergy Scoring

**File:** `engine/synergy.py`

Synergy is computed only between commander and each candidate card individually. This misses:

- **Card-to-card synergy**: Ashnod's Altar + Reassembling Skeleton is a combo, but neither scores high with a sacrifice commander individually
- **Enabler/payoff relationships**: Sacrifice outlets are enablers, death triggers are payoffs. The current system doesn't distinguish these roles.
- **Tribal matching**: `_THEME_PATTERNS["tribal"]` detects "lord" effects but never checks if the candidate's creature type matches the commander's tribe. A Zombie lord scores the same with an Elf tribal commander as with a Zombie tribal commander.
- **Combo detection**: No awareness of known 2-3 card combos (e.g., Exquisite Blood + Sanguine Bond, Mikaeus + Triskelion)

**Improvement path:**
1. **Short-term**: Add creature type matching for tribal commanders (extract creature type from commander's type_line, boost cards sharing that type)
2. **Short-term**: Build a combo database (JSON file of known 2-card and 3-card combos), boost cards that form combos with the commander or with already-selected cards
3. **Medium-term**: Compute pairwise synergy for the top N candidates, not just commander-candidate synergy. Use this to detect "packages" of cards that work together.
4. **Long-term**: Use LLM to generate a synergy matrix for the top 200 candidates per build. Cache per commander.

### W3: EDHREC Rank as Power Proxy

**File:** `engine/deck_builder.py` (`_normalize_edhrec_rank`)

EDHREC rank measures **popularity across all decks**, not quality in a specific deck. Sol Ring is rank 1 because it goes in every deck, not because it's the best card for every commander.

- A card ranked #500 might be the perfect card for a niche commander but scores the same as any other #500 card
- Cards with no rank default to 0.3, which is arbitrary

**Improvement path:**
1. **Short-term**: Use EDHREC's per-commander data if available (they have "% of decks running this card" per commander). This would require a new data source.
2. **Medium-term**: Weight EDHREC rank by theme relevance — a card popular in "counter" decks should score higher with a counter-focused commander than its global rank suggests.
3. **Long-term**: Train a simple scoring model on EDHREC decklists. Features: card keywords, commander keywords, theme overlap, category. Target: inclusion rate in top-performing decklists.

### W4: Static Category Targets

**File:** `engine/deck_builder.py` (`DEFAULT_CATEGORY_TARGETS`)

The 8x8 framework uses fixed targets (8 ramp, 8 draw, etc.) regardless of commander strategy:

- A spell-slinger commander wants more card draw and fewer creatures
- A creature-based commander wants more creatures and less removal
- A stax deck wants more stax pieces and fewer win conditions
- A combo deck needs fewer generic goodstuff and more specific combo pieces

**Improvement path:**
1. **Short-term**: Define 4-5 archetype profiles (aggro, control, combo, midrange, spellslinger) with different category targets. Detect archetype from commander themes.
2. **Medium-term**: Let the LLM research phase suggest category ratios as part of its structured output (add `"category_targets"` to the research JSON schema).
3. **Long-term**: Learn optimal category ratios from EDHREC top decklists per commander.

### W5: No Mana Curve Shaping During Selection

**File:** `engine/deck_builder.py`

The mana curve is only **analyzed** post-build (in `analyzer.py`). During card selection, a deck can end up with 15 five-drops and 2 two-drops if those happened to score highest.

**Improvement path:**
1. **Short-term**: Add a soft CMC distribution target to the budget optimizer. Penalize selecting another card at a CMC bucket that's already overfull.
2. **Medium-term**: Use the commander's ideal curve profile (aggro wants low curve, control wants higher) to weight CMC preferences during selection.

### W6: No Card Redundancy Awareness

The algorithm can select 12 similar card draw spells when 8 would be enough and the remaining 4 slots would be better served by removal or protection.

**Improvement path:**
1. **Short-term**: After filling a category to its max target, apply a diminishing returns penalty to additional cards in that category.
2. **Medium-term**: Detect functional duplicates (cards with very similar oracle text) and penalize selecting too many.

### W7: No Deck-Internal Synergy

Cards are scored only against the commander, never against each other. A deck with Skullclamp + token generators is stronger than the sum of its parts, but the algorithm doesn't see this.

**Improvement path:**
1. **Medium-term**: After initial selection, run a "synergy audit" — compute pairwise synergy for all 100 cards, identify low-synergy outliers, and swap them for cards that synergize better with the selected pool.
2. **Long-term**: Use a graph-based approach where cards are nodes and synergy edges have weights. Optimize for maximum total edge weight.

### W8: Win Condition Detection is Narrow

**File:** `engine/categories.py` (`_WIN_CONDITION_PATTERNS`)

Only matches "you win the game" and "each opponent loses". Misses:
- Combat-based win conditions (big creatures, evasion, extra combats)
- Infinite combo pieces
- Alternative win conditions (mill, infect, commander damage enablers)
- Value engines that generate inevitability

**Improvement path:**
1. **Short-term**: Expand win condition patterns to include extra combats, infect, "deals X damage to each opponent", high-power creatures with evasion keywords
2. **Medium-term**: Tag known combo pieces from the combo database (see W2) as win conditions when they appear together

## Improvement Priority Matrix

| ID | Weakness | Impact | Effort | Priority | Status |
|----|----------|--------|--------|----------|--------|
| W4 | Static category targets | High | Low | **P0** | **DONE** — Archetype enum + detect_archetype() + per-archetype targets |
| W2a | Tribal matching | High | Low | **P0** | **DONE** — _extract_creature_types() + _compute_tribal_synergy() in synergy.py |
| W2b | Combo database | High | Medium | **P1** | **DONE** — CommanderSpellbook API + fallback JSON + combo_repo + synergy integration |
| W3a | Per-commander EDHREC data | High | High | **P2** | **DONE** — EDHREC JSON API + edhrec_repo + lazy fetch/cache in CLI + scoring integration |
| W5 | No curve shaping | High | Medium | **P1** | **DONE** — IDEAL_CURVE per archetype + compute_curve_penalty() in budget_optimizer + wired into build_deck |
| W1a | Expand regex patterns | Medium | Low | **P1** | **DONE** — 28 new patterns: treasure/food ramp, impulsive draw, scry/surveil/connive, fight/bounce/sacrifice removal, ward/phase out protection, mass bounce/damage wipes |
| W8 | Narrow win conditions | Medium | Low | **P1** | **DONE** — 20 new patterns: infect/toxic/poison, extra combat, mill, damage to each opponent, double strike, power doubling + infect theme in synergy.py |
| W6 | No redundancy awareness | Medium | Low | **P1** | **DONE** — compute_diminishing_penalty() + compute_functional_similarity() (Jaccard) + compute_duplicate_penalty() in budget_optimizer |
| W2c | Pairwise synergy | High | High | **P2** | **DONE** — compute_pairwise_synergy() + compute_package_score() + find_synergy_packages() in synergy.py |
| W7 | Deck-internal synergy | High | High | **P2** | **DONE** — audit_synergy() in synergy_audit.py: pairwise audit, outlier detection, swap suggestions |
| W1b | LLM-assisted categorization | High | Medium | **P2** | **DONE** — LLMCategorizer in advisor/llm_categorizer.py: batched LLM categorization with parsing + validation |
| W4b | LLM-suggested category ratios | Medium | Low | **P2** | **DONE** — category_targets field in ResearchResult, LLM prompt extended, validated parsing |
| W3b | Trained scoring model | Very High | Very High | **P3** | **Partial** — ml/features.py, ml/trainer.py, ml/predictor.py implemented + engine integration. Training pipeline needs numpy (optional dep). |
| W2d | LLM synergy matrix | High | Medium | **P3** | **DONE** — advisor/llm_synergy.py + db/llm_synergy_repo.py + budget_optimizer integration |

## Measurement: How Do We Know Decks Got Better?

Without measurement, we're guessing. Every algorithm change should be validated.

### Automated Metrics (implement first)
- **Category coverage score**: % of minimum targets met (ramp >= 8, draw >= 8, etc.)
- **Mana curve smoothness**: Standard deviation from ideal curve distribution
- **Synergy density**: Average pairwise synergy score across all card pairs
- **Budget efficiency**: Total card quality per dollar spent
- **EDHREC overlap**: % of selected cards that appear in EDHREC's average decklist for that commander (requires EDHREC average list data)

### A/B Testing Framework
Build a `DeckComparison` tool that:
1. Generates two decks for the same commander with different algorithm versions
2. Computes all metrics above for both
3. Outputs a comparison table
4. Optionally asks the LLM "which of these two decklists is stronger and why?"

### Manual Validation
- Build decks for 5-10 well-known commanders (Atraxa, Korvold, Muldrotha, Krenko, Talrand)
- Compare output against EDHREC average lists
- Track "WTF cards" — selections that make no sense to an experienced player
- Regression test: save "golden" decklists and diff against them when the algorithm changes

## Data Sources to Integrate

| Source | What It Provides | Status |
|--------|-----------------|--------|
| Scryfall Bulk | Card data, oracle text, prices, printings | Integrated |
| EDHREC Rank (via Scryfall) | Global card popularity | Integrated |
| EDHREC Average Decklist API | Per-commander card inclusion rates | **Integrated** — edhrec_repo + lazy CLI fetch |
| EDHREC Commander Pages | Theme breakdowns, combo lists | Not integrated |
| MTGGoldfish | Price trends, format metagame | Not integrated |
| CommanderSpellbook | Verified 2-3 card combos | **Integrated** — API + fallback JSON + combo_repo |

## Architecture Principle

**The algorithm should degrade gracefully across capability tiers:**

```
Tier 0 (no data):     Random legal cards within color identity
Tier 1 (Scryfall):    Regex categorization + EDHREC rank + budget optimizer
Tier 2 (+ combos):    Combo DB + tribal matching + curve shaping + archetype profiles + redundancy awareness
Tier 3 (+ EDHREC):    Per-commander inclusion rates + average list comparison
Tier 4 (+ LLM):       LLM-guided categorization + synergy matrix + adaptive targets  <-- CURRENT
Tier 5 (+ learning):  Trained models from EDHREC data, user feedback loop  <-- PARTIALLY REACHED (ML predictor integrated, training pipeline present)
```

Each tier should be independently testable and the system should always work at Tier 1 even if higher-tier data sources are unavailable.

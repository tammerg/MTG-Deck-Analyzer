# MTG Commander Deck Creator - Implementation Plan

## Project Overview

A CLI-based Magic: The Gathering Commander deck builder that generates optimized decklists at various budget tiers, outputs well-formatted CSVs, and provides intelligent upgrade recommendations for existing decks.

---

## Architecture

### Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **CLI Framework**: Click
- **Data Storage**: SQLite (local card/price cache)
- **CSV I/O**: Python stdlib `csv` module (no pandas dependency)
- **HTTP Client**: httpx (async support)
- **AI/LLM**: Claude API (anthropic SDK) for natural language deck advice
- **Testing**: pytest with TDD, VCR-style fixtures for API mocking

### API Integrations (Priority Order)

| API | Purpose | Auth | Cost |
|-----|---------|------|------|
| **Scryfall** | Card data, legality, images, daily prices | User-Agent header only | Free |
| **MTGJSON** | Bulk card data for local DB seeding | None | Free |
| **Scryfall Prices** | Baseline pricing (USD, EUR) - fallback/offline mode | None | Free |
| **TCGAPIs** | Real-time TCGPlayer pricing (hourly updates) | API Key | Free tier: 100 calls/day |
| **JustTCG** | Fallback/supplementary pricing | API Key | Free tier: 1,000 calls/month |

> **Note**: EDHREC has no official API. We build our own synergy scoring engine inspired by EDHREC's "lift" methodology using Scryfall card data. Community libraries like `pyedhrec` can be integrated later as supplementary data.

### Project Structure

```
mtg_deck_maker/
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   └── mtg_deck_maker/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI entry point (thin wrapper)
│       ├── config.py               # Config loading: CLI > env > file > defaults
│       ├── models/
│       │   ├── __init__.py
│       │   ├── card.py             # Card data model (oracle-level)
│       │   ├── printing.py         # Printing data model (set-level)
│       │   ├── deck.py             # Deck data model
│       │   └── commander.py        # Commander model (partners, backgrounds, companions)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── scryfall.py         # Scryfall API client
│       │   ├── pricing.py          # TCGAPIs / JustTCG client
│       │   └── rate_limiter.py     # Shared rate limiting
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py         # SQLite connection & schema versioning
│       │   ├── schema.sql          # Full schema definition
│       │   ├── card_repo.py        # Card data access layer
│       │   ├── printing_repo.py    # Printing data access layer
│       │   └── price_repo.py       # Price data access layer
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── deck_builder.py     # Core deck generation algorithm
│       │   ├── budget_optimizer.py # Budget-aware card selection (soft caps)
│       │   ├── mana_base.py        # Mana base construction
│       │   ├── synergy.py          # Synergy/lift scoring engine
│       │   ├── categories.py       # Card categorization (ramp, draw, removal, etc.)
│       │   └── power_level.py      # Power level estimation
│       ├── services/
│       │   ├── __init__.py
│       │   ├── build_service.py    # Orchestrate: sync → load commander → build → validate → price → export
│       │   ├── analyze_service.py  # Orchestrate: import → categorize → analyze → report
│       │   ├── upgrade_service.py  # Orchestrate: import → analyze → recommend → price → report
│       │   ├── advise_service.py   # Orchestrate: import → analyze → LLM context → advice
│       │   └── sync_service.py     # Orchestrate: MTGJSON seed → Scryfall sync → update printings → refresh tags
│       ├── advisor/
│       │   ├── __init__.py
│       │   ├── upgrade.py          # Deck upgrade recommendations
│       │   ├── analyzer.py         # Deck weakness analysis
│       │   └── llm_advisor.py      # Claude API integration for NL advice
│       ├── io/
│       │   ├── __init__.py
│       │   ├── csv_export.py       # CSV output formatting
│       │   └── csv_import.py       # CSV deck import & parsing (standard, Moxfield, Archidekt)
│       └── utils/
│           ├── __init__.py
│           ├── colors.py           # Color identity helpers
│           └── formatting.py       # Display/output formatting
├── tests/
│   ├── conftest.py                 # Shared fixtures, VCR cassettes
│   ├── fixtures/                   # VCR cassettes for API responses
│   │   ├── scryfall/
│   │   └── pricing/
│   ├── golden/                     # Golden decklist files for regression
│   ├── test_api/
│   │   ├── test_scryfall.py
│   │   └── test_pricing.py
│   ├── test_engine/
│   │   ├── test_deck_builder.py
│   │   ├── test_budget_optimizer.py
│   │   ├── test_mana_base.py
│   │   ├── test_synergy.py
│   │   └── test_categories.py
│   ├── test_services/
│   │   ├── test_build_service.py
│   │   └── test_sync_service.py
│   ├── test_io/
│   │   ├── test_csv_export.py
│   │   └── test_csv_import.py
│   └── test_advisor/
│       ├── test_upgrade.py
│       └── test_analyzer.py
└── data/
    └── .gitkeep                    # SQLite DB and bulk data stored here
```

---

## Database Schema

Normalized schema separating oracle-level cards from set-level printings, with proper price mapping.

```sql
-- Cards are oracle-level entities (unique rules text)
CREATE TABLE cards (
  id INTEGER PRIMARY KEY,
  oracle_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  type_line TEXT,
  oracle_text TEXT,
  mana_cost TEXT,
  cmc REAL,
  colors TEXT,              -- e.g., "W,U"
  color_identity TEXT,      -- e.g., "W,U"
  keywords TEXT,            -- comma-separated list
  edhrec_rank INTEGER,
  legal_commander INTEGER DEFAULT 0,
  legal_brawl INTEGER DEFAULT 0,
  updated_at TEXT
);

-- Printings are set-level entities (unique physical print)
CREATE TABLE printings (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  scryfall_id TEXT UNIQUE NOT NULL,
  set_code TEXT NOT NULL,
  collector_number TEXT NOT NULL,
  lang TEXT DEFAULT 'en',
  rarity TEXT,
  finishes TEXT,            -- comma-separated: "nonfoil,foil,etched"
  tcgplayer_id INTEGER,
  cardmarket_id INTEGER,
  released_at TEXT,
  is_promo INTEGER DEFAULT 0,
  is_reprint INTEGER DEFAULT 0,
  UNIQUE(card_id, set_code, collector_number, lang)
);

-- Faces for MDFCs and split cards
CREATE TABLE card_faces (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  face_index INTEGER NOT NULL,
  face_name TEXT,
  mana_cost TEXT,
  type_line TEXT,
  oracle_text TEXT,
  colors TEXT
);

-- Pricing per printing, per finish, per source
CREATE TABLE prices (
  id INTEGER PRIMARY KEY,
  printing_id INTEGER NOT NULL REFERENCES printings(id),
  source TEXT NOT NULL,             -- scryfall, tcgplayer, cardmarket, justtcg
  currency TEXT NOT NULL DEFAULT 'USD',
  price REAL,
  finish TEXT DEFAULT 'nonfoil',    -- nonfoil, foil, etched
  retrieved_at TEXT NOT NULL
);

-- Card categorization tags with confidence
CREATE TABLE card_tags (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  tag TEXT NOT NULL,                -- ramp, draw, removal, board_wipe, win_condition, etc.
  confidence REAL DEFAULT 1.0,
  UNIQUE(card_id, tag)
);

-- Commander pair relationships (partner, background, companion)
CREATE TABLE commander_pairs (
  id INTEGER PRIMARY KEY,
  partner_a INTEGER NOT NULL REFERENCES cards(id),
  partner_b INTEGER REFERENCES cards(id),    -- null for solo commanders
  background INTEGER REFERENCES cards(id),   -- for "Choose a Background"
  companion INTEGER REFERENCES cards(id)     -- companion card if applicable
);

-- Persisted decklists
CREATE TABLE decks (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  format TEXT DEFAULT 'commander',
  budget_target REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE deck_cards (
  id INTEGER PRIMARY KEY,
  deck_id INTEGER NOT NULL REFERENCES decks(id),
  card_id INTEGER NOT NULL REFERENCES cards(id),
  quantity INTEGER DEFAULT 1,
  category TEXT,
  is_commander INTEGER DEFAULT 0,
  is_companion INTEGER DEFAULT 0
);

-- ID mappings for cross-API resolution
CREATE TABLE id_mappings (
  id INTEGER PRIMARY KEY,
  oracle_id TEXT NOT NULL,
  scryfall_id TEXT,
  tcgplayer_id INTEGER,
  cardmarket_id INTEGER,
  UNIQUE(oracle_id, scryfall_id)
);

-- Schema version tracking
CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_cards_name ON cards(name);
CREATE INDEX idx_cards_color_identity ON cards(color_identity);
CREATE INDEX idx_cards_legal_commander ON cards(legal_commander);
CREATE INDEX idx_printings_card_id ON printings(card_id);
CREATE INDEX idx_printings_tcgplayer_id ON printings(tcgplayer_id);
CREATE INDEX idx_prices_printing_id ON prices(printing_id);
CREATE INDEX idx_prices_retrieved_at ON prices(retrieved_at);
CREATE INDEX idx_card_tags_card_id ON card_tags(card_id);
CREATE INDEX idx_card_tags_tag ON card_tags(tag);
```

---

## Core Features

### Feature 1: Card Database & Price Cache

**Goal**: Maintain a local SQLite database of all Commander-legal cards with current pricing.

**Implementation**:
1. Seed DB from MTGJSON bulk data on first run (populates `cards` + `printings`)
2. Daily sync with Scryfall for new cards, legality changes, and baseline prices
3. On-demand pricing lookups via TCGAPIs/JustTCG for real-time market prices
4. Cache prices with TTL (24h for bulk, 1h for individual lookups)
5. **Offline mode**: Falls back to Scryfall-cached prices when external pricing APIs are unavailable

**Price Selection Policy**:
1. Gather prices for all printings of a card
2. Filter by language = `en`
3. Filter by finish preference (default: nonfoil)
4. Apply source priority: `tcgplayer > cardmarket > scryfall > justtcg`
5. Choose lowest price within source group
6. If missing, mark as "price unknown" with warning

### Feature 2: Commander Deck Generation

**Goal**: Given a commander name and budget, generate a complete 100-card Commander deck.

**CLI Interface**:
```bash
# Generate a deck
mtg-deck build "Atraxa, Praetors' Voice" --budget 150 --output atraxa_deck.csv

# Generate at multiple budget tiers
mtg-deck build "Atraxa, Praetors' Voice" --budgets 50 150 500 --output atraxa_decks/

# Specify power level target
mtg-deck build "Korvold, Fae-Cursed King" --budget 200 --power-level 7

# Partner commanders
mtg-deck build "Thrasios, Triton Hero" --partner "Tymna the Weaver" --budget 300

# With constraints
mtg-deck build "Ur-Dragon" --budget 200 --config my_constraints.toml
```

**Commander Validation**:
- Confirm card exists and is Commander-legal
- Detect Partner, Choose a Background, Companion keywords
- Compute union color identity for partner pairs
- Enforce companion restriction rules if applicable

**Deck Building Algorithm** (8x8-inspired):

1. **Validate Commander** (including partner/background/companion support)
2. **Determine Color Identity** (union of all commander components)
3. **Build Category Targets** (flexible 8x8):
   - Ramp: 8-12 cards
   - Card Draw: 8-10 cards
   - Removal (targeted): 5-7 cards
   - Board Wipes: 2-4 cards
   - Win Conditions: 7-10 cards
   - Commander Synergy: 8-12 cards
   - Protection/Recursion: 3-5 cards
   - Utility/Flex: remaining slots
4. **Select Lands** (budget-aware):
   - Base count: 34-37 (adjusted by color count, commander CMC, and ramp density)
   - Budget allocation: ~30% of budget for mana base at mid-range+
   - Prioritize untapped sources at higher budgets
   - Consider color pip requirements for land selection
5. **Fill Categories** (budget-optimized with soft caps):
   - Score candidates by: `synergy_score * power_score / price_weight`
   - Use soft budget caps per category (can exceed if total stays in budget)
   - Backfill underfilled categories from overflow
   - Ensure mandatory staples where budget allows
6. **Validate Deck**:
   - Exactly 100 cards (99 + commander, or 98 + 2 partners)
   - All cards within color identity
   - All cards Commander-legal
   - No duplicate cards (singleton format)
   - Mana curve distribution check
   - Total price within budget (5% tolerance)
7. **Output CSV**

### Feature 3: CSV Export Format

**Standard Output Columns**:
```csv
Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes
1,"Atraxa, Praetors' Voice",Commander,"{G}{W}{U}{B}",4,Legendary Creature,12.50,Phyrexia All Will Be One,ONE,Commander
1,Sol Ring,Ramp,"{1}",1,Artifact,3.00,Commander 2021,C21,Staple
1,Command Tower,Land,,0,Land,0.25,Commander 2021,C21,Staple
...
```

**Summary Section** (appended after card list):
```csv
,,,,,,,,
,DECK SUMMARY,,,,,,,
,Total Cards:,100,,,,,,
,Total Price:,$147.50,,,,,,
,Average CMC:,3.2,,,,,,
,Colors:,"W,U,B,G",,,,,,
,Commander:,"Atraxa, Praetors' Voice",,,,,,
,Budget Target:,$150.00,,,,,,
,Prices As Of:,2026-02-18,,,,,,
```

### Feature 4: CSV Import & Deck Analysis

**Goal**: Import an existing deck from CSV and provide analysis.

**CLI Interface**:
```bash
# Analyze an existing deck
mtg-deck analyze my_deck.csv

# Get upgrade suggestions with a budget
mtg-deck upgrade my_deck.csv --budget 25 --focus "card-draw"

# Get help with a specific problem
mtg-deck advise my_deck.csv --problem "I keep running out of cards by turn 6"

# Validate deck legality
mtg-deck validate my_deck.csv
```

**Import Parser**:
- Accept standard CSV (Quantity, Card Name minimum)
- Also accept Moxfield/Archidekt export formats
- Fuzzy match card names against local card database
- Flag unrecognized cards with suggestions
- Detect format automatically

### Feature 5: Upgrade Recommendations

**Goal**: Given a deck and a budget, recommend the highest-impact upgrades.

**Algorithm**:
1. Analyze current deck composition (category balance, mana curve, synergy score)
2. Identify weaknesses (missing categories, poor mana base, low synergy cards)
3. Score each potential swap: `upgrade_value = (new_synergy - old_synergy) * power_delta / new_price`
4. Rank swaps by upgrade_value within budget
5. Output swap recommendations with reasoning (card out -> card in, price delta, why)

**Upgrade Modes**:
- **Budget Upgrade**: "I have $X to spend" - maximize power-per-dollar
- **Problem-Focused**: "My deck struggles with X" - targeted category improvements
- **Power Level Push**: "Move this deck from level 5 to level 7" - systematic optimization

### Feature 6: LLM-Powered Advice (Claude Integration)

**Goal**: Natural language deck advice using Claude API.

**Implementation**:
- Pass structured deck analysis (composition, categories, curve, price breakdown) as context
- Support conversational queries about strategy, meta, and card choices
- Claude provides reasoning for suggestions, not just card lists
- **Strictly optional** - all core features work without LLM
- Rate-limited to manage API costs
- Configurable via `ANTHROPIC_API_KEY` env var

---

## Constraints Configuration

User-defined constraints shape deck behavior. Loaded with precedence: **CLI flags > env vars > config file > defaults**.

**`.mtg-deck-maker.toml` example**:
```toml
[constraints]
avoid_reserved_list = true
avoid_infinite_combos = true
max_price_per_card = 20.0
allow_tutors = true
allow_fast_mana = false
include_staples = true
prefer_nonfoil = true
exclude_cards = ["Mana Crypt", "Dockside Extortionist"]
force_cards = ["Skullclamp"]

[pricing]
preferred_source = "tcgplayer"  # tcgplayer, cardmarket, scryfall
preferred_currency = "USD"
preferred_finish = "nonfoil"
price_policy = "cheapest_print"  # cheapest_print, latest_print, specific_set

[general]
data_dir = "./data"
cache_ttl_hours = 24
offline_mode = false
```

---

## Budget Tier Definitions

| Tier | Range | Mana Base Budget | Power Level | Key Differences |
|------|-------|------------------|-------------|-----------------|
| Ultra-Budget | $25-50 | ~$5-10 | 2-4 | Taplands, basics, limited ramp |
| Budget | $50-100 | ~$15-25 | 4-6 | Pain lands, signets, basic staples |
| Mid-Range | $100-250 | ~$40-75 | 5-7 | Shock lands, good removal suite |
| High-Power | $250-500 | ~$100-175 | 7-8 | Fetch lands, strong tutors |
| Competitive | $500-1000 | ~$200-400 | 8-9 | Full fetch/shock, fast mana |
| cEDH | $1000+ | ~$400+ | 9-10 | Original duals, Mana Crypt, fully optimized |

---

## MVP Algorithm: Rule-Based Card Categorization

### Stage 1: Category Tagging Rules (oracle_text keyword matching)

| Category | Keyword/Phrase Patterns |
|----------|------------------------|
| **Ramp** | "search your library for a.*land", "add {", mana_cost contains only generic + type is Artifact (mana rocks) |
| **Card Draw** | "draw a card", "draw.*cards", "investigate", "create.*Clue" |
| **Removal (targeted)** | "destroy target", "exile target", "deals.*damage to.*target" |
| **Board Wipe** | "destroy all", "exile all", "each.*gets -" |
| **Counterspell** | "counter target spell", "counter target.*ability" |
| **Protection** | "hexproof", "indestructible", "shroud", "protection from" |
| **Recursion** | "return.*from.*graveyard", "reanimate" |
| **Win Condition** | "you win the game", "each opponent loses", "commander damage", "infinite" (flagged) |
| **Tutor** | "search your library for a card" (non-land) |

**Negative filters**: Exclude reminder text matches, flavor text, etc.

### Stage 2: Candidate Scoring

```
base_score = category_weight + commander_synergy_score
commander_synergy_score = keyword_overlap(commander, candidate) * theme_multiplier
power_score = cmc_efficiency + effect_quality_proxy
final_score = base_score * power_score / price_weight
```

### Stage 3: Selection with Soft Budgets

1. Fill each category from top-scored candidates
2. If a category underfills due to budget, borrow from flex allocation
3. If total exceeds budget, swap lowest-scored cards for cheaper alternatives
4. Add lands last based on color pip analysis and curve needs
5. Validate and output

---

## Implementation Phases (Revised)

### Phase 1: Foundation + Schema
1. Project scaffolding (pyproject.toml, uv setup, directory structure, .gitignore)
2. Config loader with precedence (CLI > env > file > defaults)
3. SQLite database with full schema and version tracking
4. Card and Printing data models
5. Database repository layer (card_repo, printing_repo, price_repo)
6. Tests for schema, models, and repositories

### Phase 2: Data Seeding + Sync
1. MTGJSON bulk data downloader and importer
2. Scryfall API client with rate limiting
3. Scryfall bulk data sync (cards, printings, baseline prices)
4. Card categorization engine (rule-based oracle_text tagging)
5. `sync_service.py` orchestration
6. Tests with VCR cassettes for API responses

### Phase 3: CSV I/O Layer
1. CSV export with full metadata and summary section
2. CSV import with auto-format detection (standard, Moxfield, Archidekt)
3. Fuzzy card name matching against local DB
4. Deck analysis output formatting
5. Tests for import/export round-trips

### Phase 4: Deck Building Engine
1. Commander validation (solo, partner, background, companion)
2. Color identity computation (union for pairs)
3. Mana base builder (budget-aware, color-pip-aware land selection)
4. Synergy scoring engine (keyword overlap + oracle_text analysis)
5. Category-based card selection with soft budget optimization
6. 8x8 framework implementation with flexible slots
7. Deck validation (legality, singleton, count, budget, curve)
8. Power level estimation
9. `build_service.py` orchestration
10. Deterministic generation (seeded RNG for reproducibility)
11. Tests with golden decklists for regression

### Phase 5: Pricing Engine
1. TCGAPIs client with API key management
2. JustTCG client as fallback
3. Price selection policy (source priority, finish preference, cheapest print)
4. Price caching layer with TTL
5. Price confidence scoring (age, source reliability)
6. Offline mode (Scryfall-only fallback)
7. `price_repo` integration with build/upgrade services
8. Tests for pricing accuracy and caching

### Phase 6: Advisor & Upgrade Engine
1. Deck composition analyzer (identify weaknesses by category)
2. Upgrade recommendation algorithm (swap scoring)
3. Budget-constrained swap optimization
4. Problem-focused advisor (NL problem -> category mapping, no LLM needed)
5. `upgrade_service.py` and `analyze_service.py` orchestration
6. Tests for recommendation quality

### Phase 7: LLM Advisor (Optional)
1. Claude API integration for conversational advice
2. Structured deck context builder (analysis -> prompt)
3. `advise_service.py` orchestration
4. Graceful degradation when API key not configured
5. Tests (mocked LLM responses)

### Phase 8: CLI & Polish
1. Click CLI with all commands: `build`, `analyze`, `upgrade`, `advise`, `validate`, `sync`, `search`, `config`
2. Progress indicators for long operations (Rich library)
3. Error handling and user-friendly messages
4. Error boundaries (single API failure doesn't crash `build`)
5. End-to-end integration tests
6. Property-based tests for legality invariants

---

## Key Technical Decisions

### Why Python?
- Strong ecosystem for data manipulation and SQLite
- httpx for async HTTP with rate limiting
- Click is the gold standard for CLI tools
- Anthropic SDK available natively
- Rapid prototyping for algorithm iteration

### Why SQLite?
- Zero-infrastructure local storage
- Excellent for single-user CLI application
- Full SQL for complex card queries
- Built into Python stdlib

### Why stdlib `csv` over pandas?
- Dramatically smaller dependency footprint for a CLI tool
- CSV operations are simple (no dataframe manipulation needed)
- Faster startup time

### Synergy Scoring Approach
Self-contained engine using Scryfall data:
1. Keyword/oracle_text matching for synergy detection
2. Commander keyword overlap scoring
3. Category tagging via rule-based oracle text parsing
4. Iteratively refineable with LLM-assisted tagging in future

### Deterministic Generation
- Seeded RNG for reproducible deck builds
- Same commander + budget + constraints = same deck
- Useful for testing and comparison

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits | Aggressive local caching, bulk data imports, respect rate limits |
| Pricing API unavailable | Offline mode with Scryfall-cached prices, clear "prices as of" timestamps |
| Price data staleness | TTL-based cache refresh, price confidence scoring, age warnings |
| Card categorization accuracy | Confidence scores, manual override via config, iterative improvement |
| Budget calculation drift | Latest cached prices, 5% tolerance, "price unknown" warnings |
| New set releases | Automated Scryfall sync detects new cards |
| Scryfall/MTGJSON ID mismatch | `id_mappings` table, oracle_id as canonical key |
| Single API failure | Error boundaries - fallback behavior per feature, never crash |
| LLM costs | Strictly optional, rate-limited, configurable |
| Partner/MDFC edge cases | Explicit commander_pairs table, card_faces for split cards |

---

## Success Criteria

1. Generate a valid, playable Commander deck in <30 seconds
2. Deck stays within specified budget (5% tolerance)
3. CSV output imports cleanly into spreadsheet software
4. Support solo commanders, partner pairs, backgrounds, and companions
5. Upgrade recommendations measurably improve deck composition scores
6. Support all color identities including colorless
7. Price data no more than 24 hours stale for cached, 1 hour for on-demand
8. All core features work without LLM (offline-capable except pricing)
9. Deterministic builds (same inputs = same outputs)

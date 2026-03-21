# MTG Commander Deck Builder -- Web Frontend Architecture Plan

## Executive Summary

A React + TypeScript SPA backed by a FastAPI layer that wraps the existing Python services. The API exposes the same operations the CLI performs (search, build, advise, research, sync) as REST endpoints. The frontend renders card data using Scryfall image URLs stored in the printings table, with no image proxying needed. The backend owns all database access and LLM orchestration; the frontend is purely presentational and stateless beyond local UI state.

---

## 1. Tech Stack

### Frontend

| Choice | Justification |
|--------|---------------|
| **React 19 + TypeScript** | Component model fits the card-heavy UI. Largest ecosystem for MTG-related components. |
| **Vite** | Fast dev server, native TS support. Lighter than Next.js -- no SSR needed since this is a local tool with a local DB. |
| **TanStack Query (React Query)** | Handles async server state with caching, retry, loading/error states out of the box. |
| **Tailwind CSS v4** | Utility-first, rapid prototyping, good dark-theme support for MTG aesthetics. |
| **React Router v7** | Client-side routing for the SPA. |

### Backend API

| Choice | Justification |
|--------|---------------|
| **FastAPI** | Already in the Python ecosystem. Type-hinted request/response models map directly to existing dataclasses. Built-in OpenAPI/Swagger docs. Async support for long-running LLM calls. |
| **Pydantic v2** | FastAPI's native serialization layer. Mirrors existing dataclass models with validation. |
| **uvicorn** | ASGI server for FastAPI. |

### Why NOT Next.js

The application is a local developer tool with a local SQLite database. SSR, edge functions, and Vercel deployment add complexity without benefit. A Vite SPA that talks to a local FastAPI server is simpler and matches the existing architecture.

---

## 2. Backend API Layer

### 2.1 API Module Location

New package: `src/mtg_deck_maker/api/web/`

Sits alongside the existing `api/scryfall.py` module.

### 2.2 Endpoint Design

All endpoints return JSON. Long-running operations use HTTP with streaming progress or simple blocking responses.

#### Cards & Search

```
GET  /api/cards/search?q={query}&color={WUB}&type={creature}&limit=50
GET  /api/cards/{card_id}
GET  /api/cards/{card_id}/printings
GET  /api/cards/{card_id}/price
GET  /api/commanders/search?q={query}
```

#### Deck Building

```
POST /api/decks/build
  Body: { commander: string, partner?: string, budget: number, seed?: number, smart?: boolean, provider?: string }
  Response: { deck: DeckResponse, warnings: string[] }

GET  /api/decks/{deck_id}
GET  /api/decks
DELETE /api/decks/{deck_id}

POST /api/decks/{deck_id}/export
  Body: { format: "csv" | "moxfield" | "archidekt" }
  Response: text/csv or text/plain
```

#### Analysis & Advice

```
POST /api/decks/{deck_id}/analyze
  Response: { category_breakdown, mana_curve, avg_cmc, power_level, recommendations, ... }

POST /api/decks/{deck_id}/advise
  Body: { question: string, provider?: string }
  Response: { advice: string }

POST /api/research
  Body: { commander: string, budget?: number, provider?: string }
  Response: { strategy_overview, key_cards, budget_staples, combos, win_conditions, cards_to_avoid }
```

#### System

```
POST /api/sync
  Body: { full: boolean }
  Response: SSE stream with progress events, final SyncResult

GET  /api/config
PUT  /api/config
  Body: partial config object

GET  /api/health
  Response: { status: "ok", db_exists: boolean, card_count: number }
```

### 2.3 Response Models (Pydantic)

**CardResponse** -- maps from `Card` dataclass:
```
oracle_id, name, type_line, oracle_text, mana_cost, cmc, colors, color_identity,
keywords, edhrec_rank, legal_commander, id
```
Plus computed fields: `image_url` (from scryfall_id), `price` (cheapest USD nonfoil).

**DeckCardResponse** -- maps from `DeckCard`:
```
card_id, quantity, category, is_commander, is_companion,
card_name, cmc, colors, price, mana_cost, type_line, oracle_text, image_url
```

**DeckResponse** -- maps from `Deck`:
```
id, name, format, budget_target, created_at, cards: list[DeckCardResponse],
total_cards, total_price, average_cmc, color_distribution, commanders
```

### 2.4 Database Connection Management

FastAPI dependency injection wraps the existing `Database` context manager. `get_db()` yields a `Database` instance per request.

### 2.5 Image URL Construction

Scryfall image URLs follow a deterministic pattern:

```
https://cards.scryfall.io/{size}/front/{id[0]}/{id[1]}/{scryfall_id}.jpg
```

New method needed: `PrintingRepository.get_primary_printing(card_id)` -- returns the most relevant English, non-promo printing for image URL construction.

---

## 3. Component Architecture

### 3.1 Component Tree (top-level)

```
App
  Layout
    Header (nav, logo)
    Main
      <Route> HomePage
      <Route> BuildPage
      <Route> DeckViewPage
      <Route> ResearchPage
      <Route> SearchPage
      <Route> SettingsPage
    Footer
```

### 3.2 Page-Level Components

| Component | Responsibility |
|-----------|---------------|
| `HomePage` | Landing page. Shows recent decks, quick commander search, CTA to build. |
| `BuildPage` | Commander selection, build config form, triggers build, shows progress, redirects to DeckViewPage on completion. |
| `DeckViewPage` | Full deck display: commander card, categorized card list, stats panel, mana curve chart, export controls, advise panel. |
| `ResearchPage` | Commander research form. Displays ResearchResult: strategy overview, key cards grid, combos, win conditions. |
| `SearchPage` | Full card database search with filters. |
| `SettingsPage` | Config display/edit, sync trigger with progress, API key status. |

### 3.3 Shared/Feature Components

| Component | Props / Responsibility |
|-----------|----------------------|
| `CardImage` | `{ scryfallId, size? }`. Scryfall image with lazy loading, skeleton, error fallback. |
| `CardTooltip` | Wraps any element; on hover shows card image + oracle text overlay. |
| `CardListItem` | Single row: name, mana cost (symbols), type, category badge, price. |
| `CardGrid` | Grid of card images with names. |
| `DeckCategoryGroup` | Collapsible group header with card count, contains CardListItems. |
| `CommanderBanner` | Large card image(s), name, color identity pips, type line. |
| `ManaCurveChart` | Bar chart of CMC distribution. |
| `ColorDistribution` | Pie/donut chart of color spread. |
| `DeckStats` | Stats panel: total cards, total price, avg CMC, power level. |
| `ManaSymbol` | Renders a single mana symbol image from Scryfall SVG CDN. |
| `ManaCost` | Parses `{2}{W}{U}` and renders a row of ManaSymbols. |
| `ColorPips` | Color identity as a row of colored circles. |
| `PriceTag` | Price with color coding (green/yellow/red relative to budget). |
| `CommanderSearch` | Autocomplete input with debounce, shows results dropdown with card images. |
| `BuildConfigForm` | Budget slider, strategy options, smart toggle, seed input. |
| `AdvisePanel` | Text input for question, displays LLM response with markdown rendering. |
| `ExportMenu` | Dropdown with CSV, Moxfield, Archidekt export options. |
| `SyncProgress` | Triggers sync, shows SSE progress, completion status. |
| `LoadingCard` | Skeleton placeholder matching card dimensions. |

---

## 4. Page/Route Structure

| Route | Page | Description |
|-------|------|-------------|
| `/` | `HomePage` | Recent decks list, quick build CTA |
| `/build` | `BuildPage` | Commander search + build configuration + build trigger |
| `/deck/:deckId` | `DeckViewPage` | Full deck display, analysis, export, advise |
| `/research` | `ResearchPage` | Commander research via LLM |
| `/search` | `SearchPage` | Database card search with filters |
| `/settings` | `SettingsPage` | Config, sync, API key status |

---

## 5. Data Flow

### 5.1 Card Data Pipeline

```
Scryfall Bulk Download
    --> sync_service.py (existing)
        --> SQLite: cards, printings, prices tables

FastAPI Request
    --> card_repo / price_repo / printing_repo (existing)
        --> Pydantic response model (adds image_url from scryfall_id)
            --> JSON response

React Component
    --> TanStack Query fetch
        --> Component renders card data
        --> <CardImage> loads scryfall_id --> constructs image URL --> <img>
```

### 5.2 Deck Build Flow

```
User fills BuildConfigForm on BuildPage
    --> POST /api/decks/build { commander, budget, ... }
        --> FastAPI handler:
            1. card_repo.get_card_by_name(commander)
            2. card_repo.get_cards_by_color_identity(colors)
            3. price_repo.get_cheapest_price() for pool
            4. (if smart) research_service.research_commander()
            5. build_service.build(commander, budget, pool, prices, priority_cards)
            6. Persist deck to DB (decks + deck_cards tables)
            7. Return DeckResponse with all cards enriched with images/prices
    --> React receives DeckResponse
        --> Navigate to /deck/:deckId
        --> DeckViewPage renders
```

### 5.3 Image Flow

Card images are never proxied or cached by the backend. The frontend loads them directly from Scryfall's CDN:

```
CardImage component receives scryfallId
    --> Constructs URL: https://cards.scryfall.io/{size}/front/{id[0]}/{id[1]}/{id}.jpg
    --> <img src={url} loading="lazy" />
    --> Browser caches via standard HTTP cache headers (Scryfall sets long cache TTLs)
```

---

## 6. Card Image Handling

### 6.1 Scryfall Image URL Pattern

```
Base: https://cards.scryfall.io
Sizes: small (146x204), normal (488x680), large (672x936), png (745x1040)
Pattern: /{size}/front/{id[0]}/{id[1]}/{scryfall_id}.jpg
```

### 6.2 Strategy

| Concern | Approach |
|---------|----------|
| **Loading** | Native `loading="lazy"` on all card images. |
| **Placeholders** | CSS skeleton with card dimensions (2.5:3.5 ratio). |
| **Error handling** | `onError` fallback to bundled card-back image. |
| **Size selection** | `small` for lists/tooltips, `normal` for grids, `large` for commander banner. |
| **MDFC/Split** | Front face default, flip button toggles `/front/` and `/back/`. |
| **Caching** | Browser HTTP cache (Scryfall: `Cache-Control: max-age=604800`). |
| **Batch preload** | First 20 card image URLs as `<link rel="preload">` for above-the-fold. |

---

## 7. State Management

### TanStack Query + React Context (no Redux)

| State Type | Management |
|------------|-----------|
| **Server data** (cards, decks, search results, LLM responses) | TanStack Query. Cached by query key. |
| **Build form state** | React `useState` local to `BuildPage`. Lifted to URL params. |
| **UI state** (sidebar, tabs, sort) | React `useState` local to components. |
| **App-wide config** | React Context via `ConfigProvider`. Hydrated from `/api/config`. |
| **Build progress** | TanStack Query mutation state. |
| **Sync progress** | SSE EventSource + local `useState`. |

### Query Key Convention

```
["cards", "search", { q, color, type }]
["cards", cardId]
["commanders", "search", { q }]
["decks"]
["decks", deckId]
["decks", deckId, "analysis"]
["research", commanderName]
["config"]
["health"]
```

---

## 8. Styling: Tailwind CSS v4 + Custom Theme

### MTG WUBRG Color Palette

| Token | Use |
|-------|-----|
| `--color-mana-w` (#F9FAF4) | White mana |
| `--color-mana-u` (#0E68AB) | Blue mana |
| `--color-mana-b` (#150B00) | Black mana |
| `--color-mana-r` (#D3202A) | Red mana |
| `--color-mana-g` (#00733E) | Green mana |
| `--color-budget-ok` | Price within budget (green) |
| `--color-budget-warn` | Price near budget (yellow) |
| `--color-budget-over` | Price over budget (red) |

- **Dark mode** as default (MTG aesthetic). Light mode toggle.
- **Card aspect ratio**: `aspect-[5/7]` (standard MTG card ratio).
- **Typography**: System font stack. Mana symbols via Scryfall SVG CDN.

---

## 9. Project Structure

```
src/mtg_deck_maker/
  api/
    web/                          # NEW - FastAPI app
      __init__.py
      app.py                      # FastAPI application factory
      dependencies.py             # get_db(), get_config() deps
      routers/
        __init__.py
        cards.py                  # /api/cards/* endpoints
        decks.py                  # /api/decks/* endpoints
        research.py               # /api/research endpoint
        sync.py                   # /api/sync endpoint
        config.py                 # /api/config endpoints
        health.py                 # /api/health endpoint
      schemas/
        __init__.py
        card.py                   # CardResponse, CardSearchParams
        deck.py                   # DeckResponse, BuildRequest, DeckCardResponse
        research.py               # ResearchRequest, ResearchResponse
        config.py                 # ConfigResponse, ConfigUpdate
        sync.py                   # SyncRequest, SyncProgress
      middleware.py               # CORS, error handling

frontend/                         # NEW - React SPA
  package.json
  tsconfig.json
  vite.config.ts
  tailwind.config.ts
  index.html
  public/
    card-back.jpg                 # Fallback card image
    favicon.svg
  src/
    main.tsx                      # React entry point
    App.tsx                       # Router setup
    api/
      client.ts                   # Axios/fetch wrapper, base URL config
      cards.ts                    # Card API functions
      decks.ts                    # Deck API functions
      research.ts                 # Research API functions
      sync.ts                     # Sync API + SSE helpers
      config.ts                   # Config API functions
      types.ts                    # TypeScript interfaces matching Pydantic schemas
    components/
      layout/
        Header.tsx
        Footer.tsx
        Layout.tsx
        Sidebar.tsx
      card/
        CardImage.tsx
        CardTooltip.tsx
        CardListItem.tsx
        CardGrid.tsx
        ManaCost.tsx
        ManaSymbol.tsx
        ColorPips.tsx
        PriceTag.tsx
        LoadingCard.tsx
      deck/
        CommanderBanner.tsx
        DeckCategoryGroup.tsx
        DeckStats.tsx
        ManaCurveChart.tsx
        ColorDistribution.tsx
        ExportMenu.tsx
        AdvisePanel.tsx
      search/
        CommanderSearch.tsx
        CardSearchFilters.tsx
        SearchResults.tsx
      build/
        BuildConfigForm.tsx
        BuildProgress.tsx
      settings/
        SyncProgress.tsx
        ConfigEditor.tsx
        ApiKeyStatus.tsx
    pages/
      HomePage.tsx
      BuildPage.tsx
      DeckViewPage.tsx
      ResearchPage.tsx
      SearchPage.tsx
      SettingsPage.tsx
    hooks/
      useCardSearch.ts
      useDeckBuild.ts
      useResearch.ts
      useDeck.ts
      useConfig.ts
    context/
      ConfigContext.tsx
    utils/
      scryfall.ts                 # Image URL construction, mana symbol parsing
      format.ts                   # Price formatting, color names
      categories.ts               # Category display names, icons, colors
    styles/
      globals.css                 # Tailwind base + custom properties
```

---

## 10. Development Phases

### Phase 1: API Foundation (Backend)

- New package: `src/mtg_deck_maker/api/web/`
- All REST endpoints wrapping existing services
- New `PrintingRepository.get_primary_printing()` method
- Add `fastapi`, `uvicorn` to `pyproject.toml`
- New CLI command: `mtg-deck serve`
- CORS middleware for `localhost:5173`

### Phase 2: Frontend Scaffold + Card Display

- Initialize `frontend/` with Vite + React + TypeScript
- Install: tailwindcss, @tanstack/react-query, react-router, axios
- Implement: Layout, Header, routing
- Implement: CardImage, ManaCost, ManaSymbol, ColorPips, PriceTag, LoadingCard
- Implement: SearchPage with filters
- Implement: API client layer + useCardSearch hook
- Implement: scryfall.ts utility

### Phase 3: Deck Building UI

- CommanderSearch autocomplete with debounce
- BuildConfigForm + BuildPage
- Full DeckViewPage with all sub-components
- HomePage with recent decks

### Phase 4: LLM Features (Research + Advise)

- ResearchPage with form and result display
- AdvisePanel on DeckViewPage
- Markdown rendering for LLM responses

### Phase 5: Settings, Sync, Export, Polish

- SettingsPage with config, sync, API key status
- ExportMenu (CSV, Moxfield, Archidekt)
- SSE sync progress
- Error boundaries, loading states, responsive design, keyboard nav
- `mtg-deck serve` CLI command

---

## Dependencies

### Backend (`pyproject.toml`)

```
fastapi>=0.115
uvicorn[standard]>=0.32
```

### Frontend (`frontend/package.json`)

```
react, react-dom, @types/react, @types/react-dom
typescript
vite, @vitejs/plugin-react
tailwindcss
@tanstack/react-query
react-router
axios
react-markdown (Phase 4)
vitest, @testing-library/react, @testing-library/jest-dom (dev)
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **SQLite concurrent access** | Single process, Database per-request, WAL mode. |
| **LLM blocking event loop** | FastAPI runs sync endpoints in thread pool automatically. |
| **Large card pool queries** | Pagination on search endpoints. |
| **Scryfall CDN dependency** | Fallback card-back bundled locally. CardImage handles onError. |
| **Missing printings** | API returns `image_url: null`, frontend renders placeholder. |
| **Stale DB** | Health endpoint returns last sync timestamp. Settings shows warning. |

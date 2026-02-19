# Phase 2: Multi-Provider LLM Integration (ChatGPT + Claude)

> Plan reviewed by OpenAI Codex — feedback incorporated below.

## Overview

Add OpenAI/ChatGPT support alongside the existing Anthropic/Claude integration, enabling deep commander research, LLM-enhanced deck building, and provider-agnostic advice. Users can use whichever API key they have (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).

## Current State (Phase 1 Complete — 647 tests passing)

- **LLM module**: `advisor/llm_advisor.py` — single-provider, hardcoded to Anthropic Claude
- **Service**: `services/advise_service.py` — wraps `get_deck_advice()` for the `advise` CLI command
- **Config**: No LLM settings in `AppConfig`; API key read from `ANTHROPIC_API_KEY` env var
- **Dependency**: `anthropic>=0.40` in `pyproject.toml`

---

## Architecture

### 1. Provider Abstraction (`advisor/llm_provider.py`) — NEW

Abstract base class with a messages-based interface (per Codex review: avoid over-simplifying to hide SDK differences).

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],  # [{"role": "system"|"user"|"assistant", "content": "..."}]
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 60.0,
    ) -> str:
        """Send a chat message and return the text response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider has a valid API key AND the SDK is installed."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name (e.g. 'OpenAI ChatGPT')."""
        ...

def get_provider(preferred: str = "auto", config: LLMConfig | None = None) -> LLMProvider | None:
    """Resolve an LLM provider.

    Args:
        preferred: "openai", "anthropic", or "auto" (tries openai first, then anthropic).
        config: Optional LLMConfig for model/timeout settings.

    Returns:
        An available LLMProvider, or None if no API keys are set.
    """
```

**Design note (Codex feedback):** The messages list approach avoids hiding the system prompt semantics difference between OpenAI (system message in messages array) and Anthropic (separate system parameter). Each provider translates messages internally.

### 2. Anthropic Provider (`advisor/anthropic_provider.py`) — NEW

Extract existing Claude logic from `llm_advisor.py`:

```python
class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model

    def chat(self, messages, *, max_tokens=1024, temperature=0.7, timeout_s=60.0) -> str:
        # Extracts system message from messages list, passes as `system` param to Anthropic SDK
        # Includes retry with exponential backoff for 429/5xx
        ...

    def is_available(self) -> bool:
        # Checks: API key is set AND anthropic SDK is importable AND model name is non-empty
        ...

    @property
    def name(self) -> str: return "Anthropic Claude"
```

### 3. OpenAI Provider (`advisor/openai_provider.py`) — NEW

New ChatGPT integration with **lazy import** (per Codex review: `openai` should be optional):

```python
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model

    def chat(self, messages, *, max_tokens=1024, temperature=0.7, timeout_s=60.0) -> str:
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "OpenAI provider requires the 'openai' package. "
                "Install with: pip install mtg-deck-maker[openai]"
            )
        # Includes retry with exponential backoff for 429/5xx
        # Timeout via httpx timeout param
        ...

    def is_available(self) -> bool:
        # Checks: API key is set AND openai SDK is importable
        ...

    @property
    def name(self) -> str: return "OpenAI ChatGPT"
```

### 4. Retry & Timeout Policy (Codex recommendation — both providers)

Each provider implements:
- **Timeout**: Configurable per-request timeout (default 60s), passed to SDK client
- **Retries**: Exponential backoff for 429 (rate limit) and 5xx errors, max 3 retries
- **Token budget**: Research prompts truncate oracle_text input if excessively long

```python
# Shared retry logic in advisor/retry.py
def with_retries(fn, max_retries=3, backoff_base=2.0) -> str:
    """Execute fn() with exponential backoff on rate limit / server errors."""
```

### 5. Commander Research Service (`services/research_service.py`) — NEW

Deep commander research powered by LLM:

```python
@dataclass(slots=True)
class ResearchResult:
    commander_name: str
    strategy_overview: str
    key_cards: list[str]
    budget_staples: list[str]
    combos: list[str]
    win_conditions: list[str]
    cards_to_avoid: list[str]
    raw_response: str            # Full LLM response for reference
    parse_success: bool = True   # Whether structured parsing succeeded

class ResearchService:
    def __init__(self, provider: LLMProvider | None = None): ...

    def research_commander(
        self,
        commander_name: str,
        oracle_text: str = "",
        color_identity: list[str] | None = None,
        budget: float | None = None,
    ) -> ResearchResult: ...
```

**Prompt strategy (Codex feedback incorporated):**

The research prompt asks the LLM to return a JSON block inside a fenced code block for reliable parsing:

```
You are an expert Magic: The Gathering Commander deck builder.
Analyze the following commander and provide your recommendations.

Commander: {name}
Oracle Text: {oracle_text}
Color Identity: {colors}
Budget: ${budget} (if specified)

Respond with a JSON object inside a ```json fenced code block with these exact keys:
{
  "strategy_overview": "...",
  "key_cards": ["card1", "card2", ...],
  "budget_staples": ["card1", "card2", ...],
  "combos": ["description1", "description2", ...],
  "win_conditions": ["win con 1", "win con 2", ...],
  "cards_to_avoid": ["card1", "card2", ...]
}

Limit key_cards to 15 max, budget_staples to 10 max, combos to 5 max.
If unsure about a section, use an empty list.
```

**Parser logic:**
1. Extract JSON from fenced code block using regex
2. Parse with `json.loads()`
3. If parsing fails, set `parse_success = False` and populate `raw_response` only
4. When used by `--smart`, **only apply priority cards if `parse_success is True`** (Codex recommendation)

### 6. LLM-Enhanced Build (`--smart` flag)

Add `--smart` flag to the `build` command:

```
mtg-deck build "Atraxa, Praetors' Voice" --budget 100 --smart
```

Flow:
1. Look up commander in DB (existing)
2. **NEW**: Call `ResearchService.research_commander()` to get `key_cards` list
3. Cross-reference `key_cards` with the local card pool from DB (fuzzy name matching)
4. Boost priority scores for matched cards in the deck builder
5. Build deck as normal with LLM-recommended cards weighted higher

**Scoring adjustment (Codex feedback):** The +500 bonus is configurable via config and capped so it doesn't completely dominate. Cards must still pass color identity and budget filters. If no provider is available, `--smart` prints a message and proceeds with normal build (no crash).

Implementation changes:
- `BuildService.build()`: Add optional `priority_cards: list[str]` parameter
- `engine/deck_builder.py`: In the scoring step, add configurable bonus for priority-matched cards

### 7. Refactor `llm_advisor.py` — MODIFY

Refactor `get_deck_advice()` to use the provider abstraction:

```python
def get_deck_advice(
    deck_analysis: DeckAnalysis,
    question: str,
    provider: LLMProvider | None = None,
    api_key: str | None = None,           # Kept for backward compat, deprecated
) -> str:
```

If `provider` is passed, use it. Otherwise call `get_provider("auto")`.

### 8. Config Changes (`config.py`) — MODIFY

Add `LLMConfig` dataclass:

```python
@dataclass(slots=True)
class LLMConfig:
    provider: str = "auto"                          # "openai", "anthropic", or "auto"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout_s: float = 60.0
    max_retries: int = 3
    research_enabled: bool = True
    priority_bonus: int = 500                       # Score boost for LLM-recommended cards
```

Add to `AppConfig`:
```python
@dataclass(slots=True)
class AppConfig:
    constraints: ConstraintsConfig = ...
    pricing: PricingConfig = ...
    general: GeneralConfig = ...
    llm: LLMConfig = field(default_factory=LLMConfig)  # NEW
```

**Env var overrides (Codex feedback: split by provider):**
- `MTG_LLM_PROVIDER` -> `llm.provider`
- `MTG_OPENAI_MODEL` -> `llm.openai_model`
- `MTG_ANTHROPIC_MODEL` -> `llm.anthropic_model`
- `MTG_LLM_TIMEOUT` -> `llm.timeout_s`
- `MTG_LLM_MAX_RETRIES` -> `llm.max_retries`

**TOML:**
```toml
[llm]
provider = "openai"
openai_model = "gpt-4o"
anthropic_model = "claude-sonnet-4-20250514"
max_tokens = 2048
temperature = 0.7
timeout_s = 60.0
max_retries = 3
priority_bonus = 500
```

### 9. New CLI Command: `research` — NEW

```
mtg-deck research "Atraxa, Praetors' Voice" [--budget 100] [--provider openai] [--model gpt-4o] [--format rich|json|md]
```

Output formats (Codex recommendation: add `--format` for automation):
- `rich` (default): Rich-formatted terminal output with tables and colors
- `json`: Raw JSON for piping to other tools
- `md`: Markdown for saving to file

Example Rich output:
```
Researching: Atraxa, Praetors' Voice (W/U/B/G)
Using: OpenAI ChatGPT (gpt-4o)

Strategy Overview
  Atraxa excels as a +1/+1 counters or Superfriends commander...

Key Cards (15)
  - Doubling Season ($45.00)
  - Deepglow Skate ($8.00)
  ...

Budget Staples (10)
  - Evolution Sage ($0.25)
  - Grateful Apparition ($0.30)
  ...

Notable Combos
  - Doubling Season + any planeswalker = instant ultimate
  ...

Win Conditions
  - Planeswalker ultimates
  - Infect (Atraxa proliferates poison counters)
  ...

Cards to Avoid
  - Vorinclex, Monstrous Raider (high salt score, draws hate)
  ...
```

### 10. Updated `advise` & `config` Commands — MODIFY

**advise:** Add `--provider` and `--model` flags:
```
mtg-deck advise deck.csv --problem "Too slow" --provider openai --model gpt-4o
```

**config --show:** Display LLM settings and API key status for both providers:
```
LLM Settings
  Provider: auto
  OpenAI model: gpt-4o
  Anthropic model: claude-sonnet-4-20250514
  OPENAI_API_KEY: configured
  ANTHROPIC_API_KEY: not set
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `advisor/llm_provider.py` | NEW | Abstract LLMProvider base + `get_provider()` factory |
| `advisor/openai_provider.py` | NEW | OpenAI/ChatGPT provider (lazy import) |
| `advisor/anthropic_provider.py` | NEW | Extracted from `llm_advisor.py` |
| `advisor/retry.py` | NEW | Shared retry/backoff logic |
| `advisor/llm_advisor.py` | MODIFY | Refactor to use provider abstraction |
| `services/research_service.py` | NEW | Commander research service with JSON parsing |
| `services/advise_service.py` | MODIFY | Accept provider parameter |
| `services/build_service.py` | MODIFY | Add `priority_cards` param for `--smart` |
| `engine/deck_builder.py` | MODIFY | Add priority card scoring boost |
| `config.py` | MODIFY | Add `LLMConfig` dataclass + TOML/env loading |
| `cli.py` | MODIFY | Add `research` command, `--smart` flag, `--provider`/`--model` flags |
| `pyproject.toml` | MODIFY | Add `openai>=1.40` as optional dependency |

### Test Files

| File | Action | Description |
|------|--------|-------------|
| `tests/test_advisor/test_llm_provider.py` | NEW | Provider abstraction + `get_provider()` tests |
| `tests/test_advisor/test_openai_provider.py` | NEW | OpenAI provider tests (mocked SDK) |
| `tests/test_advisor/test_anthropic_provider.py` | NEW | Anthropic provider tests (mocked SDK) |
| `tests/test_advisor/test_retry.py` | NEW | Retry/backoff logic tests |
| `tests/test_services/test_research_service.py` | NEW | Research service + JSON parser tests |
| `tests/test_cli.py` | MODIFY | Tests for `research`, `--smart`, `--provider` |
| `tests/test_config.py` | MODIFY | `LLMConfig` default/override tests |

---

## Implementation Order

1. **Provider abstraction** — `llm_provider.py`, `anthropic_provider.py`, `openai_provider.py`, `retry.py`
2. **Config updates** — `LLMConfig` dataclass, TOML/env loading, config tests
3. **Refactor advisor** — Update `llm_advisor.py` and `advise_service.py` to use providers
4. **Research service** — `research_service.py` with JSON-in-fenced-block prompt + parser
5. **Research CLI command** — `mtg-deck research` with `--format rich|json|md`
6. **Smart build** — Priority cards in deck builder + `--smart` CLI flag
7. **Tests** — All new modules, failure modes, parser edge cases, updated CLI tests

---

## Dependencies

```toml
[project]
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "anthropic>=0.40",
    "rich>=13.0",
    "thefuzz[speedup]>=0.22",
]

[project.optional-dependencies]
openai = ["openai>=1.40"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "vcrpy>=6.0",
]
all = ["mtg-deck-maker[openai]"]
```

Users install OpenAI support with: `pip install mtg-deck-maker[openai]`

---

## Test Coverage Requirements (Codex feedback)

Beyond happy-path tests, ensure coverage for:

- [ ] Provider `is_available()` when SDK missing (ImportError)
- [ ] Provider `is_available()` when API key absent
- [ ] Provider `chat()` on 429 rate limit (verify retry behavior)
- [ ] Provider `chat()` on 5xx server error (verify retry + give up)
- [ ] Provider `chat()` on timeout
- [ ] Research JSON parser with malformed response (missing keys, no fenced block)
- [ ] Research JSON parser with partial response (some sections empty)
- [ ] `--smart` when no provider available (graceful skip, not crash)
- [ ] `--smart` when `parse_success is False` (skip priority cards, build normally)
- [ ] `--provider openai` with missing OpenAI key (targeted error message)
- [ ] `--provider anthropic` with missing Anthropic key (targeted error message)
- [ ] Config `LLMConfig` defaults load correctly
- [ ] Config env var overrides for all LLM settings
- [ ] Config TOML `[llm]` section parsing
- [ ] `config --show` displays both API key statuses (SET/NOT SET, no values leaked)

---

## Design Decisions

1. **"auto" provider resolution**: When `provider = "auto"`, try `OPENAI_API_KEY` first (more widely held), then `ANTHROPIC_API_KEY`. Configurable in TOML.

2. **Graceful degradation**: All LLM features are optional. If no API key is set, `--smart` prints a message and proceeds with normal build, `research` and `advise` print clear instructions.

3. **JSON-in-fenced-block for research** (Codex recommendation): More reliable than markdown heading parsing. Regex extracts ```json ... ``` block, `json.loads()` parses it. If parsing fails, `parse_success = False` and raw response is preserved.

4. **Priority card scoring**: Configurable bonus (default +500). Cards must still pass color identity and budget filters. Bonus is additive to existing synergy/EDHREC scores, not a multiplier — prevents complete domination.

5. **Optional `openai` dependency**: Lazy-imported in `OpenAIProvider`. Users without OpenAI needs don't install the SDK. Clear error message if they try `--provider openai` without it.

6. **Messages-based provider interface** (Codex recommendation): `chat(messages=[...])` instead of `chat(system, user)` avoids hiding the system prompt semantics difference between OpenAI and Anthropic.

7. **Model flexibility**: Users can choose models per-provider via config or `--model` CLI flag. Defaults: `gpt-4o` and `claude-sonnet-4-20250514`.

---

## Codex Review Notes

The following concerns from Codex review were incorporated into this plan:

| Concern | Resolution |
|---------|-----------|
| Provider abstraction too narrow | Changed to messages-based interface with temperature/timeout |
| Research parsing fragile | Switched to JSON-in-fenced-block with `parse_success` flag |
| No retry/timeout policy | Added `retry.py` module, configurable timeout + max_retries |
| `openai` as hard dependency | Made optional via `[project.optional-dependencies]` + lazy import |
| `MTG_LLM_MODEL` env var ambiguous | Split into `MTG_OPENAI_MODEL` and `MTG_ANTHROPIC_MODEL` |
| Missing failure-mode tests | Added comprehensive test coverage checklist |
| +500 bonus may dominate | Made configurable, additive only, requires `parse_success` |
| No output format options | Added `--format rich|json|md` to research command |
| Missing `--model` CLI flag | Added to `research` and `advise` commands |

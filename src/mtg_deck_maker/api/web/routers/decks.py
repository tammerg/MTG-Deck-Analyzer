"""Decks router - build, list, get, delete, export, analyze, advise."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from mtg_deck_maker.api.web.dependencies import get_config, get_db
from mtg_deck_maker.api.web.routers.cards import _scryfall_image_url
from mtg_deck_maker.api.web.schemas.deck import (
    DeckAdviseRequest,
    DeckBuildRequest,
    DeckCardResponse,
    DeckExportRequest,
    DeckResponse,
    DeckSummaryResponse,
    DeckUpgradeRequest,
    DeckUpgradeResponse,
    StrategyGuideRequest,
    StrategyGuideResponse,
    UpgradeRecommendationResponse,
)
from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.deck_repo import DeckRepository
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck
from mtg_deck_maker.services.build_service import BuildService, BuildServiceError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decks"])


def _resolve_deck_cards(
    deck: Deck,
    card_repo: CardRepository,
) -> list[Card]:
    """Fetch all Card objects for a deck's DeckCard entries in one batch query.

    Args:
        deck: The Deck whose cards should be resolved.
        card_repo: Card repository used for the batch fetch.

    Returns:
        List of Card objects for each DeckCard that resolves to a known card.
    """
    cards_by_id = card_repo.get_cards_by_ids([dc.card_id for dc in deck.cards if dc.card_id])
    return list(cards_by_id.values())


def _deck_to_response(
    deck: Deck,
    card_repo: CardRepository,
    printing_repo: PrintingRepository,
    price_repo: PriceRepository,
) -> DeckResponse:
    """Convert a Deck model to a DeckResponse using batch DB queries.

    Fetches all cards, primary printings, and cheapest prices in 3 queries
    total regardless of deck size, eliminating the N+1 pattern.

    Args:
        deck: The Deck model to convert.
        card_repo: Card repository for metadata enrichment.
        printing_repo: Printing repository for image URLs.
        price_repo: Price repository for price lookup.

    Returns:
        DeckResponse with all computed fields populated.
    """
    card_ids = [dc.card_id for dc in deck.cards if dc.card_id]

    cards_by_id = card_repo.get_cards_by_ids(card_ids)
    printings_by_card_id = printing_repo.get_primary_printings(card_ids)
    # Single batched query regardless of deck size; cost is O(1) in round-trips.
    # Cheapest price per card is derived from prices_by_source, avoiding a
    # redundant get_cheapest_prices call.
    prices_by_source = price_repo.get_prices_by_source(card_ids)

    card_responses: list[DeckCardResponse] = []
    for dc in deck.cards:
        image_url: str | None = None
        mana_cost = ""
        type_line = ""
        oracle_text = ""
        tcgplayer_id: int | None = None

        if dc.card_id:
            card = cards_by_id.get(dc.card_id)
            if card is not None:
                mana_cost = card.mana_cost
                type_line = card.type_line
                oracle_text = card.oracle_text

            primary = printings_by_card_id.get(dc.card_id)
            if primary is not None:
                image_url = _scryfall_image_url(primary.scryfall_id)
                tcgplayer_id = primary.tcgplayer_id

        price = dc.price
        source_prices = prices_by_source.get(dc.card_id, {}) if dc.card_id else {}
        if price == 0.0 and source_prices:
            price = min(source_prices.values())

        card_responses.append(
            DeckCardResponse(
                card_id=dc.card_id,
                quantity=dc.quantity,
                category=dc.category,
                is_commander=dc.is_commander,
                card_name=dc.card_name,
                cmc=dc.cmc,
                colors=dc.colors,
                price=price,
                mana_cost=mana_cost,
                type_line=type_line,
                oracle_text=oracle_text,
                image_url=image_url,
                tcgplayer_id=tcgplayer_id,
                price_tcgplayer=source_prices.get("tcgplayer"),
            )
        )

    commanders = [c for c in card_responses if c.is_commander]

    return DeckResponse(
        id=deck.id,
        name=deck.name,
        format=deck.format,
        budget_target=deck.budget_target,
        created_at=deck.created_at,
        cards=card_responses,
        total_cards=deck.total_cards(),
        total_price=round(sum(cr.price * cr.quantity for cr in card_responses), 2),
        average_cmc=round(deck.average_cmc(), 2),
        color_distribution=deck.color_distribution(),
        commanders=commanders,
    )


@router.post("/decks/build", response_model=DeckResponse, status_code=201)
def build_deck(
    req: DeckBuildRequest,
    db: Database = Depends(get_db),
    config: AppConfig = Depends(get_config),
) -> DeckResponse:
    """Build and persist a Commander deck.

    Delegates the full build pipeline to ``BuildService.build_from_db()``
    and persists the result.

    Args:
        req: DeckBuildRequest with build parameters.

    Returns:
        DeckResponse for the newly created deck.

    Raises:
        HTTPException: 404 if commander/partner not found.
        HTTPException: 422 if the build fails validation.
        HTTPException: 500 if the build fails unexpectedly.
    """
    from mtg_deck_maker.services.build_service import CommanderNotFoundError

    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)
    price_repo = PriceRepository(db)
    deck_repo = DeckRepository(db)

    service = BuildService(config=config)
    try:
        result = service.build_from_db(
            commander_name=req.commander,
            budget=req.budget,
            db=db,
            partner_name=req.partner,
            seed=req.seed,
            smart=req.smart,
            provider=req.provider,
        )
    except CommanderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during deck build")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc

    built_deck = result.deck
    built_deck.budget_target = req.budget
    built_deck.created_at = datetime.now(timezone.utc).isoformat()

    # Persist deck
    deck_id = deck_repo.create_deck(built_deck)

    # Reload from DB to get consistent data
    saved_deck = deck_repo.get_deck(deck_id)
    if saved_deck is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve saved deck.")

    # Merge price data from in-memory build result into saved deck cards
    price_by_card_id: dict[int, float] = {}
    for dc in built_deck.cards:
        if dc.card_id is not None and dc.price > 0.0:
            price_by_card_id[dc.card_id] = dc.price

    for dc in saved_deck.cards:
        if dc.card_id in price_by_card_id:
            dc.price = price_by_card_id[dc.card_id]

    return _deck_to_response(saved_deck, card_repo, printing_repo, price_repo)


@router.get("/decks", response_model=list[DeckSummaryResponse])
def list_decks(
    db: Database = Depends(get_db),
) -> list[DeckSummaryResponse]:
    """List all persisted decks as lightweight summaries.

    Returns one aggregated SQL row per deck — no per-card enrichment queries.
    Use ``GET /decks/{deck_id}`` to retrieve a deck with full card details.

    Returns:
        List of DeckSummaryResponse objects ordered by creation date descending.
    """
    deck_repo = DeckRepository(db)
    summaries = deck_repo.list_decks_summary()
    return [
        DeckSummaryResponse(
            id=s.id,
            name=s.name,
            format=s.format,
            budget_target=s.budget_target,
            created_at=s.created_at,
            total_cards=s.total_cards,
            total_price=s.total_price,
            commander_names=s.commander_names,
        )
        for s in summaries
    ]


@router.get("/decks/{deck_id}", response_model=DeckResponse)
def get_deck(
    deck_id: int,
    db: Database = Depends(get_db),
) -> DeckResponse:
    """Get a specific deck with all its cards.

    Args:
        deck_id: The deck's database primary key.

    Returns:
        DeckResponse with full card list.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    deck_repo = DeckRepository(db)
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)
    price_repo = PriceRepository(db)

    deck = deck_repo.get_deck(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")

    return _deck_to_response(deck, card_repo, printing_repo, price_repo)


@router.delete("/decks/{deck_id}", status_code=204)
def delete_deck(
    deck_id: int,
    db: Database = Depends(get_db),
) -> None:
    """Delete a deck and all its cards.

    Args:
        deck_id: The deck's database primary key.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    deck_repo = DeckRepository(db)
    deleted = deck_repo.delete_deck(deck_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")


@router.post("/decks/{deck_id}/export")
def export_deck(
    deck_id: int,
    req: DeckExportRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Export a deck in the requested format.

    Args:
        deck_id: The deck's database primary key.
        req: Export request with format selection.

    Returns:
        Dict with content and format fields.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    from mtg_deck_maker.io.csv_export import export_deck_to_csv

    deck_repo = DeckRepository(db)
    deck = deck_repo.get_deck(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")

    if req.format == "csv":
        content = export_deck_to_csv(deck=deck, filepath=None)
    elif req.format == "moxfield":
        content = _export_moxfield(deck)
    elif req.format == "archidekt":
        content = _export_archidekt(deck)
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported format: {req.format}"
        )

    return {"content": content, "format": req.format, "deck_id": deck_id}


def _export_moxfield(deck: Deck) -> str:
    """Export deck in Moxfield-compatible CSV format."""
    lines = ["Count,Name,Edition,Foil,Condition,Language,Purchase Price"]
    for dc in deck.cards:
        prefix = ""
        if dc.is_commander:
            prefix = "Commander: "
        lines.append(
            f'{dc.quantity},{prefix}{dc.card_name},,,,,'
        )
    return "\n".join(lines)


def _export_archidekt(deck: Deck) -> str:
    """Export deck in Archidekt-compatible format."""
    lines = []
    for dc in deck.cards:
        category = dc.category or ("Commander" if dc.is_commander else "Main")
        lines.append(f"{dc.quantity}x {dc.card_name} [{category}]")
    return "\n".join(lines)


@router.post("/decks/{deck_id}/analyze")
def analyze_deck(
    deck_id: int,
    db: Database = Depends(get_db),
) -> dict:
    """Run analysis on a persisted deck.

    Args:
        deck_id: The deck's database primary key.

    Returns:
        DeckAnalysis data as a dict.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    from mtg_deck_maker.advisor.analyzer import analyze_deck as _analyze_deck
    from mtg_deck_maker.engine.categories import bulk_categorize

    deck_repo = DeckRepository(db)
    card_repo = CardRepository(db)

    deck = deck_repo.get_deck(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")

    cards = _resolve_deck_cards(deck, card_repo)
    categories = bulk_categorize(cards)
    analysis = _analyze_deck(cards, categories)

    return {
        "deck_id": deck_id,
        "category_breakdown": analysis.category_breakdown,
        "mana_curve": {str(k): v for k, v in analysis.mana_curve.items()},
        "color_distribution": analysis.color_distribution,
        "avg_cmc": analysis.avg_cmc,
        "weak_categories": analysis.weak_categories,
        "strong_categories": analysis.strong_categories,
        "total_price": analysis.total_price,
        "power_level": analysis.power_level,
        "recommendations": analysis.recommendations,
    }


@router.post("/decks/{deck_id}/advise")
def advise_deck(
    deck_id: int,
    req: DeckAdviseRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Get AI-powered advice for a deck.

    Args:
        deck_id: The deck's database primary key.
        req: Advise request with question and provider.

    Returns:
        Dict with deck_id, question, and advice fields.

    Raises:
        HTTPException: 404 if the deck is not found.
        HTTPException: 503 if no LLM provider is available.
    """
    from mtg_deck_maker.advisor.analyzer import analyze_deck as _analyze_deck
    from mtg_deck_maker.advisor.llm_provider import get_provider
    from mtg_deck_maker.engine.categories import bulk_categorize
    from mtg_deck_maker.services.advise_service import AdviseService

    deck_repo = DeckRepository(db)
    card_repo = CardRepository(db)

    deck = deck_repo.get_deck(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")

    cards = _resolve_deck_cards(deck, card_repo)
    categories = bulk_categorize(cards)
    analysis = _analyze_deck(cards, categories)

    llm = get_provider(req.provider)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No LLM provider available. "
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
            ),
        )

    advise_svc = AdviseService(provider=llm)
    advice = advise_svc.get_advice(analysis, req.question)

    return {
        "deck_id": deck_id,
        "question": req.question,
        "advice": advice,
    }


@router.post(
    "/decks/{deck_id}/strategy-guide",
    response_model=StrategyGuideResponse,
)
def strategy_guide(
    deck_id: int,
    req: StrategyGuideRequest,
    db: Database = Depends(get_db),
) -> StrategyGuideResponse:
    """Generate a strategy guide for a deck.

    Args:
        deck_id: The deck's database primary key.
        req: Strategy guide request with simulation parameters.

    Returns:
        StrategyGuideResponse with analysis and optional LLM narrative.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    from mtg_deck_maker.advisor.llm_provider import get_provider
    from mtg_deck_maker.services.strategy_guide_service import StrategyGuideService

    llm = get_provider(req.provider)

    service = StrategyGuideService()
    try:
        guide = service.generate(
            deck_id=deck_id,
            db=db,
            llm_provider=llm,
            seed=req.seed,
            num_sims=req.num_simulations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Strategy guide generation failed")
        raise HTTPException(status_code=500, detail="An internal error occurred") from exc

    return StrategyGuideResponse(
        archetype=guide.archetype,
        themes=guide.themes,
        win_paths=[
            {"name": wp.name, "cards": wp.cards, "description": wp.description, "combo_id": wp.combo_id}
            for wp in guide.win_paths
        ],
        game_phases=[
            {"phase_name": gp.phase_name, "turn_range": gp.turn_range,
             "priorities": gp.priorities, "key_cards": gp.key_cards, "description": gp.description}
            for gp in guide.game_phases
        ],
        hand_simulation={
            "total_simulations": guide.hand_simulation.total_simulations,
            "keep_rate": guide.hand_simulation.keep_rate,
            "avg_land_count": guide.hand_simulation.avg_land_count,
            "avg_ramp_count": guide.hand_simulation.avg_ramp_count,
            "avg_cmc_in_hand": guide.hand_simulation.avg_cmc_in_hand,
            "sample_hands": [
                {"cards": sh.cards, "land_count": sh.land_count, "ramp_count": sh.ramp_count,
                 "avg_cmc": sh.avg_cmc, "has_win_enabler": sh.has_win_enabler,
                 "keep_recommendation": sh.keep_recommendation, "reason": sh.reason}
                for sh in guide.hand_simulation.sample_hands
            ],
            "mulligan_advice": guide.hand_simulation.mulligan_advice,
        } if guide.hand_simulation else None,
        key_synergies=[
            {"card_a": ks.card_a, "card_b": ks.card_b, "reason": ks.reason}
            for ks in guide.key_synergies
        ],
        llm_narrative=guide.llm_narrative,
    )


@router.post("/decks/{deck_id}/upgrade", response_model=DeckUpgradeResponse)
def upgrade_deck(
    deck_id: int,
    req: DeckUpgradeRequest,
    db: Database = Depends(get_db),
) -> DeckUpgradeResponse:
    """Get upgrade recommendations for a deck.

    Args:
        deck_id: The deck's database primary key.
        req: Upgrade request with budget and optional focus.

    Returns:
        DeckUpgradeResponse with recommended card swaps.

    Raises:
        HTTPException: 404 if the deck is not found.
    """
    from mtg_deck_maker.services.upgrade_service import UpgradeService

    deck_repo = DeckRepository(db)
    card_repo = CardRepository(db)
    price_repo = PriceRepository(db)

    deck = deck_repo.get_deck(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} not found.")

    deck_cards = _resolve_deck_cards(deck, card_repo)

    # Identify commander
    commander: Card | None = None
    for card in deck_cards:
        for dc in deck.cards:
            if dc.card_id == card.id and dc.is_commander:
                commander = card
                break
        if commander:
            break

    # Get card pool
    pool = card_repo.get_commander_legal_cards()

    # Get prices for deck cards + pool in a single bulk query
    all_ids = [c.id for c in deck_cards if c.id is not None]
    all_ids.extend(c.id for c in pool if c.id is not None)
    bulk_prices = price_repo.get_cheapest_prices(all_ids)

    # Convert card_id -> price to card_name -> price
    name_prices: dict[str, float] = {}
    for card in deck_cards + pool:
        if card.id is not None and card.id in bulk_prices:
            name_prices[card.name] = bulk_prices[card.id]

    service = UpgradeService()
    _analysis, recommendations = service.recommend_from_cards(
        deck_cards=deck_cards,
        card_pool=pool,
        prices=name_prices,
        budget=req.budget,
        commander=commander,
        focus=req.focus,
    )

    rec_responses = [
        UpgradeRecommendationResponse(
            card_out=rec.card_out.name,
            card_in=rec.card_in.name,
            price_delta=round(rec.price_delta, 2),
            reason=rec.reason,
            upgrade_score=round(rec.upgrade_score, 2),
        )
        for rec in recommendations
    ]

    total_cost = round(
        sum(max(0, r.price_delta) for r in rec_responses), 2
    )

    return DeckUpgradeResponse(
        deck_id=deck_id,
        recommendations=rec_responses,
        total_cost=total_cost,
    )

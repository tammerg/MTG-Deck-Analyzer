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
    StrategyGuideRequest,
    StrategyGuideResponse,
)
from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.deck_repo import DeckRepository
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.deck import Deck, DeckCard
from mtg_deck_maker.services.build_service import BuildService, BuildServiceError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decks"])


def _build_deck_card_response(
    dc: DeckCard,
    card_repo: CardRepository,
    printing_repo: PrintingRepository,
    price_repo: PriceRepository,
) -> DeckCardResponse:
    """Convert a DeckCard model to a DeckCardResponse.

    Enriches with card metadata and image URL where available.
    """
    image_url: str | None = None
    mana_cost = dc.card_name  # fallback
    type_line = ""
    oracle_text = ""

    if dc.card_id:
        card = card_repo.get_card_by_id(dc.card_id)
        if card is not None:
            mana_cost = card.mana_cost
            type_line = card.type_line
            oracle_text = card.oracle_text

        primary = printing_repo.get_primary_printing(dc.card_id)
        if primary is not None:
            image_url = _scryfall_image_url(primary.scryfall_id)

    price = dc.price
    if price == 0.0 and dc.card_id:
        fetched = price_repo.get_cheapest_price(dc.card_id)
        if fetched is not None:
            price = fetched

    return DeckCardResponse(
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
    )


def _deck_to_response(
    deck: Deck,
    card_repo: CardRepository,
    printing_repo: PrintingRepository,
    price_repo: PriceRepository,
) -> DeckResponse:
    """Convert a Deck model to a DeckResponse.

    Args:
        deck: The Deck model to convert.
        card_repo: Card repository for metadata enrichment.
        printing_repo: Printing repository for image URLs.
        price_repo: Price repository for price lookup.

    Returns:
        DeckResponse with all computed fields populated.
    """
    card_responses = [
        _build_deck_card_response(dc, card_repo, printing_repo, price_repo)
        for dc in deck.cards
    ]
    commanders = [c for c in card_responses if c.is_commander]

    return DeckResponse(
        id=deck.id,
        name=deck.name,
        format=deck.format,
        budget_target=deck.budget_target,
        created_at=deck.created_at,
        cards=card_responses,
        total_cards=deck.total_cards(),
        total_price=round(deck.total_price(), 2),
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
            smart=getattr(req, "smart", False),
            provider=getattr(req, "provider", "auto"),
        )
    except CommanderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during deck build")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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
        if dc.card_id and dc.price:
            price_by_card_id[dc.card_id] = dc.price

    for dc in saved_deck.cards:
        if dc.card_id in price_by_card_id:
            dc.price = price_by_card_id[dc.card_id]

    return _deck_to_response(saved_deck, card_repo, printing_repo, price_repo)


@router.get("/decks", response_model=list[DeckResponse])
def list_decks(
    db: Database = Depends(get_db),
) -> list[DeckResponse]:
    """List all persisted decks (without card details for performance).

    Returns:
        List of DeckResponse objects with empty cards lists.
    """
    deck_repo = DeckRepository(db)
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)
    price_repo = PriceRepository(db)

    decks = deck_repo.list_decks()
    return [
        _deck_to_response(d, card_repo, printing_repo, price_repo)
        for d in decks
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

    # Resolve card objects for analysis
    cards = []
    for dc in deck.cards:
        card = card_repo.get_card_by_id(dc.card_id)
        if card is not None:
            cards.append(card)

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

    cards = []
    for dc in deck.cards:
        card = card_repo.get_card_by_id(dc.card_id)
        if card is not None:
            cards.append(card)

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
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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

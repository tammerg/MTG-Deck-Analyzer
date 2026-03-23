"""Cards router - search, lookup, printings, prices, and commander search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from mtg_deck_maker.api.web.dependencies import get_db
from mtg_deck_maker.api.web.schemas.card import CardResponse, CardSearchResponse
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing

router = APIRouter(tags=["cards"])


def _scryfall_image_url(scryfall_id: str) -> str:
    """Build a Scryfall normal-size image URL from a scryfall_id."""
    return (
        f"https://cards.scryfall.io/normal/front/"
        f"{scryfall_id[0]}/{scryfall_id[1]}/{scryfall_id}.jpg"
    )


def _card_to_response(
    card: Card,
    printing_repo: PrintingRepository | None = None,
) -> CardResponse:
    """Convert a Card model to a CardResponse, optionally resolving image_url."""
    image_url: str | None = None
    if printing_repo is not None and card.id is not None:
        primary = printing_repo.get_primary_printing(card.id)
        if primary is not None:
            image_url = _scryfall_image_url(primary.scryfall_id)

    return CardResponse(
        id=card.id,  # type: ignore[arg-type]
        oracle_id=card.oracle_id,
        name=card.name,
        type_line=card.type_line,
        oracle_text=card.oracle_text,
        mana_cost=card.mana_cost,
        cmc=card.cmc,
        colors=card.colors,
        color_identity=card.color_identity,
        keywords=card.keywords,
        edhrec_rank=card.edhrec_rank,
        legal_commander=card.legal_commander,
        legal_brawl=card.legal_brawl,
        updated_at=card.updated_at,
        image_url=image_url,
    )


@router.get("/cards/search", response_model=CardSearchResponse)
def search_cards(
    q: str = Query("", description="Search term for card name"),
    color: str | None = Query(None, description="Color identity filter (e.g. WUB)"),
    type: str | None = Query(None, description="Card type filter"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Database = Depends(get_db),
) -> CardSearchResponse:
    """Search cards by name with optional color and type filters.

    Args:
        q: Search string matched against card names.
        color: Optional color identity filter (letters like WUB).
        type: Optional card type filter substring.
        limit: Maximum number of results.
        offset: Number of results to skip for pagination.

    Returns:
        CardSearchResponse with paginated results and total count.
    """
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)

    total = card_repo.count_search_cards(
        q,
        type_filter=type,
        color_filter=color,
    )
    page = card_repo.search_cards(
        q,
        type_filter=type,
        color_filter=color,
        limit=limit,
        offset=offset,
    )
    return CardSearchResponse(
        results=[_card_to_response(c, printing_repo) for c in page],
        total=total,
    )


@router.get("/cards/{card_id}", response_model=CardResponse)
def get_card(
    card_id: int,
    db: Database = Depends(get_db),
) -> CardResponse:
    """Get a single card by its database ID.

    Args:
        card_id: The card's database primary key.

    Returns:
        CardResponse for the requested card.

    Raises:
        HTTPException: 404 if the card is not found.
    """
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)

    card = card_repo.get_card_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")

    return _card_to_response(card, printing_repo)


@router.get("/cards/{card_id}/printings")
def get_card_printings(
    card_id: int,
    db: Database = Depends(get_db),
) -> list[dict]:
    """Return all printings for a given card.

    Args:
        card_id: The card's database primary key.

    Returns:
        List of printing objects with scryfall_id, set_code, image_url, etc.

    Raises:
        HTTPException: 404 if the card is not found.
    """
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)

    card = card_repo.get_card_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")

    printings: list[Printing] = printing_repo.get_printings_for_card(card_id)

    return [
        {
            "id": p.id,
            "scryfall_id": p.scryfall_id,
            "card_id": p.card_id,
            "set_code": p.set_code,
            "collector_number": p.collector_number,
            "lang": p.lang,
            "rarity": p.rarity,
            "finishes": p.finishes,
            "released_at": p.released_at,
            "is_promo": p.is_promo,
            "is_reprint": p.is_reprint,
            "image_url": _scryfall_image_url(p.scryfall_id),
        }
        for p in printings
    ]


@router.get("/cards/{card_id}/price")
def get_card_price(
    card_id: int,
    currency: str = Query("USD"),
    finish: str = Query("nonfoil"),
    db: Database = Depends(get_db),
) -> dict:
    """Get the cheapest current price for a card across all printings.

    Args:
        card_id: The card's database primary key.
        currency: Currency code (default USD).
        finish: Card finish (default nonfoil).

    Returns:
        Dict with card_id, price, currency, and finish.

    Raises:
        HTTPException: 404 if no price is available.
    """
    card_repo = CardRepository(db)
    price_repo = PriceRepository(db)

    card = card_repo.get_card_by_id(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")

    price = price_repo.get_cheapest_price(card_id, currency=currency, finish=finish)
    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price available for card {card_id}.",
        )

    return {
        "card_id": card_id,
        "card_name": card.name,
        "price": price,
        "currency": currency,
        "finish": finish,
    }


@router.get("/commanders/search", response_model=list[CardResponse])
def search_commanders(
    q: str = Query("", description="Search term for commander name"),
    limit: int = Query(50, ge=1, le=500),
    db: Database = Depends(get_db),
) -> list[CardResponse]:
    """Search for commander-legal cards by name.

    Args:
        q: Search string matched against card names.
        limit: Maximum number of results.

    Returns:
        List of commander-legal CardResponse objects.
    """
    card_repo = CardRepository(db)
    printing_repo = PrintingRepository(db)

    if q:
        results = card_repo.search_cards(q)
        results = [c for c in results if c.legal_commander]
    else:
        results = card_repo.get_commander_legal_cards()

    results = results[:limit]
    return [_card_to_response(c, printing_repo) for c in results]

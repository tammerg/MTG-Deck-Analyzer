"""Research router: LLM-powered and data-driven commander research."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider
from mtg_deck_maker.api.web.dependencies import get_db
from mtg_deck_maker.api.web.schemas.research import ResearchRequest, ResearchResponse
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.services.data_research_service import data_research_commander
from mtg_deck_maker.services.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


@router.post("/research", response_model=ResearchResponse)
def research_commander(
    req: ResearchRequest,
    db: Database = Depends(get_db),
) -> ResearchResponse:
    """Research a commander using LLM or data-driven fallback.

    If provider is "data", uses data-driven research directly.
    Otherwise, attempts LLM research and falls back to data-driven
    when no LLM provider is available.

    Args:
        req: ResearchRequest with commander name, optional budget, and provider.
        db: Database connection injected by FastAPI.

    Returns:
        ResearchResponse with strategy overview, key cards, combos, etc.

    Raises:
        HTTPException: 500 if the research call fails unexpectedly.
    """
    use_data = req.provider == "data"
    llm: LLMProvider | None = None

    if not use_data:
        llm = get_provider(req.provider)
        if llm is None:
            use_data = True

    if use_data:
        try:
            result = data_research_commander(db, req.commander, budget=req.budget)
        except Exception as exc:
            logger.exception("Data research failed for commander '%s'", req.commander)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return ResearchResponse(
            commander_name=result.commander_name,
            strategy_overview=result.strategy_overview,
            key_cards=result.key_cards,
            budget_staples=result.budget_staples,
            combos=result.combos,
            win_conditions=result.win_conditions,
            cards_to_avoid=result.cards_to_avoid,
            parse_success=result.parse_success,
            source="data",
        )

    try:
        svc = ResearchService(provider=llm)
        result = svc.research_commander(
            commander_name=req.commander,
            budget=req.budget,
        )
    except Exception as exc:
        logger.exception("LLM research failed for commander '%s'", req.commander)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ResearchResponse(
        commander_name=result.commander_name,
        strategy_overview=result.strategy_overview,
        key_cards=result.key_cards,
        budget_staples=result.budget_staples,
        combos=result.combos,
        win_conditions=result.win_conditions,
        cards_to_avoid=result.cards_to_avoid,
        parse_success=result.parse_success,
        source="llm",
    )

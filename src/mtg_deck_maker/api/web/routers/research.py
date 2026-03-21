"""Research router - LLM-powered commander research."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from mtg_deck_maker.advisor.llm_provider import get_provider
from mtg_deck_maker.api.web.schemas.research import ResearchRequest, ResearchResponse
from mtg_deck_maker.services.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


@router.post("/research", response_model=ResearchResponse)
def research_commander(req: ResearchRequest) -> ResearchResponse:
    """Research a commander using an LLM provider.

    Queries the configured LLM to produce structured deck-building
    recommendations for the given commander.

    Args:
        req: ResearchRequest with commander name, optional budget, and provider.

    Returns:
        ResearchResponse with strategy overview, key cards, combos, etc.

    Raises:
        HTTPException: 503 if no LLM provider is available.
        HTTPException: 500 if the research call fails unexpectedly.
    """
    llm = get_provider(req.provider)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No LLM provider available. "
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
            ),
        )

    try:
        svc = ResearchService(provider=llm)
        result = svc.research_commander(
            commander_name=req.commander,
            budget=req.budget,
        )
    except Exception as exc:
        logger.exception("Research failed for commander '%s'", req.commander)
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
    )

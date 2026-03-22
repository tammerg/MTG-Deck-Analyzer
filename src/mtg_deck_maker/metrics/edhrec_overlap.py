"""EDHREC overlap metric — measures how closely a deck matches EDHREC data."""

from __future__ import annotations

from dataclasses import dataclass, field

from mtg_deck_maker.models.deck import Deck


@dataclass(slots=True)
class EDHRECOverlapResult:
    """Result of comparing a deck against EDHREC per-commander inclusion data."""

    overlap_pct: float
    weighted_overlap: float
    matched_cards: int
    total_cards: int
    missing_from_edhrec: list[str] = field(default_factory=list)
    top_missing_edhrec: list[str] = field(default_factory=list)


def edhrec_overlap(
    deck: Deck, edhrec_inclusion: dict[str, float]
) -> EDHRECOverlapResult:
    """Compute what percentage of a deck's cards appear in EDHREC data.

    Only nonland mainboard cards are considered (commanders, companions,
    and lands are excluded).  Card name matching is case-insensitive.

    Args:
        deck: The deck to evaluate.
        edhrec_inclusion: Mapping of card name to EDHREC inclusion rate
            (0.0 to 1.0).

    Returns:
        An EDHRECOverlapResult with overlap statistics.
    """
    # Build a lowercase lookup for EDHREC data
    edhrec_lower: dict[str, float] = {
        name.lower(): rate for name, rate in edhrec_inclusion.items()
    }
    # Preserve original EDHREC names for top_missing_edhrec output
    edhrec_original: dict[str, str] = {
        name.lower(): name for name in edhrec_inclusion
    }

    # Filter to nonland mainboard cards
    eligible = [
        card
        for card in deck.cards
        if not card.is_commander
        and not card.is_companion
        and card.category != "land"
    ]

    total = len(eligible)
    if total == 0:
        return EDHRECOverlapResult(
            overlap_pct=0.0,
            weighted_overlap=0.0,
            matched_cards=0,
            total_cards=0,
            missing_from_edhrec=[],
            top_missing_edhrec=_top_missing(edhrec_lower, edhrec_original, set()),
        )

    matched = 0
    inclusion_sum = 0.0
    missing: list[str] = []
    deck_names_lower: set[str] = set()

    for card in eligible:
        lower_name = card.card_name.lower()
        deck_names_lower.add(lower_name)
        rate = edhrec_lower.get(lower_name)
        if rate is not None:
            matched += 1
            inclusion_sum += rate
        else:
            missing.append(card.card_name)

    overlap_pct = matched / total if total > 0 else 0.0
    weighted_overlap = inclusion_sum / matched if matched > 0 else 0.0

    return EDHRECOverlapResult(
        overlap_pct=overlap_pct,
        weighted_overlap=weighted_overlap,
        matched_cards=matched,
        total_cards=total,
        missing_from_edhrec=missing,
        top_missing_edhrec=_top_missing(
            edhrec_lower, edhrec_original, deck_names_lower
        ),
    )


def _top_missing(
    edhrec_lower: dict[str, float],
    edhrec_original: dict[str, str],
    deck_names_lower: set[str],
    limit: int = 5,
) -> list[str]:
    """Return the top N EDHREC cards (by inclusion rate) not in the deck."""
    candidates = [
        (edhrec_original[lname], rate)
        for lname, rate in edhrec_lower.items()
        if lname not in deck_names_lower
    ]
    candidates.sort(key=lambda pair: pair[1], reverse=True)
    return [name for name, _ in candidates[:limit]]

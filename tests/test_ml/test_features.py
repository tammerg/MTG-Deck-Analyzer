"""Tests for ML feature engineering (card-commander feature extraction)."""

from __future__ import annotations

import pytest

from mtg_deck_maker.ml.features import (
    FEATURE_NAMES,
    _color_overlap_ratio,
    _count_shared_keywords,
    _has_category,
    _has_type,
    _theme_overlap,
    _tribal_match,
    extract_features,
)
from mtg_deck_maker.models.card import Card


def _card(name: str = "Test Card", **kwargs) -> Card:
    """Create a Card with sensible defaults for testing."""
    defaults: dict = {
        "oracle_id": f"oid-{name}",
        "name": name,
        "type_line": "Creature",
        "oracle_text": "",
        "cmc": 3.0,
        "color_identity": [],
        "colors": [],
        "keywords": [],
    }
    defaults.update(kwargs)
    return Card(**defaults)


# A commander with well-defined attributes for interaction tests
_COMMANDER = _card(
    name="Atraxa, Praetors' Voice",
    type_line="Legendary Creature \u2014 Phyrexian Angel Horror",
    oracle_text="Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.",
    cmc=4.0,
    color_identity=["W", "U", "B", "G"],
    keywords=["Flying", "Vigilance", "Deathtouch", "Lifelink"],
)


class TestExtractFeaturesLength:
    """Verify feature vector length matches FEATURE_NAMES."""

    def test_returns_correct_length(self) -> None:
        """extract_features output length must equal len(FEATURE_NAMES)."""
        card = _card()
        features = extract_features(card, _COMMANDER)
        assert len(features) == len(FEATURE_NAMES)

    def test_feature_names_length_matches_output(self) -> None:
        """FEATURE_NAMES and extract_features must agree on count."""
        card = _card(cmc=5.0, keywords=["Flying"])
        features = extract_features(card, _COMMANDER)
        assert len(FEATURE_NAMES) == len(features) == 22


class TestCardFeatures:
    """Tests for individual card-level features."""

    def test_cmc_feature(self) -> None:
        """cmc feature should match card.cmc."""
        card = _card(cmc=5.0)
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("cmc")
        assert features[idx] == 5.0

    def test_color_count(self) -> None:
        """color_count should match len(color_identity)."""
        card = _card(color_identity=["W", "U", "B"])
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("color_count")
        assert features[idx] == 3.0

    def test_is_creature_for_creature(self) -> None:
        """is_creature should be 1.0 for creature cards."""
        card = _card(type_line="Creature \u2014 Elf Druid")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_creature")
        assert features[idx] == 1.0

    def test_is_creature_for_non_creature(self) -> None:
        """is_creature should be 0.0 for non-creature cards."""
        card = _card(type_line="Instant")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_creature")
        assert features[idx] == 0.0

    def test_is_instant(self) -> None:
        """is_instant should be 1.0 for instants."""
        card = _card(type_line="Instant")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_instant")
        assert features[idx] == 1.0

    def test_is_sorcery(self) -> None:
        """is_sorcery should be 1.0 for sorceries."""
        card = _card(type_line="Sorcery")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_sorcery")
        assert features[idx] == 1.0

    def test_is_artifact(self) -> None:
        """is_artifact should be 1.0 for artifacts."""
        card = _card(type_line="Artifact")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_artifact")
        assert features[idx] == 1.0

    def test_is_enchantment(self) -> None:
        """is_enchantment should be 1.0 for enchantments."""
        card = _card(type_line="Enchantment")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_enchantment")
        assert features[idx] == 1.0

    def test_is_planeswalker(self) -> None:
        """is_planeswalker should be 1.0 for planeswalkers."""
        card = _card(type_line="Legendary Planeswalker \u2014 Jace")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_planeswalker")
        assert features[idx] == 1.0

    def test_keyword_count(self) -> None:
        """keyword_count should match len(keywords)."""
        card = _card(keywords=["Flying", "Trample", "Haste"])
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("keyword_count")
        assert features[idx] == 3.0

    def test_oracle_length(self) -> None:
        """oracle_length should match len(oracle_text)."""
        text = "Draw two cards."
        card = _card(oracle_text=text)
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("oracle_length")
        assert features[idx] == float(len(text))


class TestCommanderFeatures:
    """Tests for commander-level features."""

    def test_commander_cmc(self) -> None:
        """commander_cmc should match commander's cmc."""
        card = _card()
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("commander_cmc")
        assert features[idx] == 4.0

    def test_commander_color_count(self) -> None:
        """commander_color_count should match commander's color identity length."""
        card = _card()
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("commander_color_count")
        assert features[idx] == 4.0


class TestInteractionFeatures:
    """Tests for card-commander interaction features."""

    def test_color_overlap_full_subset(self) -> None:
        """color_overlap should be 1.0 when card colors are a subset of commander."""
        card = _card(color_identity=["W", "U"])
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("color_overlap")
        assert features[idx] == 1.0

    def test_color_overlap_no_overlap(self) -> None:
        """color_overlap should be 0.0 when card has colors outside commander identity."""
        card = _card(color_identity=["R"])
        commander = _card(
            name="Mono Green Commander",
            color_identity=["G"],
            cmc=3.0,
        )
        features = extract_features(card, commander)
        idx = FEATURE_NAMES.index("color_overlap")
        assert features[idx] == 0.0

    def test_keyword_overlap_counts_shared(self) -> None:
        """keyword_overlap should count shared keywords."""
        card = _card(keywords=["Flying", "Trample"])
        # Commander has Flying, so overlap = 1
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("keyword_overlap")
        assert features[idx] == 1.0

    def test_theme_overlap_nonzero_for_matching(self) -> None:
        """theme_overlap should be non-zero when card matches commander themes."""
        # Atraxa cares about proliferate/counters; a +1/+1 counter card should match
        card = _card(
            oracle_text="When this creature enters, put a +1/+1 counter on target creature.",
        )
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("theme_overlap")
        assert features[idx] > 0.0

    def test_tribal_match_shared_types(self) -> None:
        """tribal_match should be 1.0 when card shares creature types."""
        # Atraxa is Phyrexian Angel Horror
        card = _card(type_line="Creature \u2014 Phyrexian Warrior")
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("tribal_match")
        assert features[idx] == 1.0


class TestCategoryFeatures:
    """Tests for category-based features."""

    def test_category_features_reflect_categorize_card(self) -> None:
        """Category features should match what categorize_card returns."""
        # A card with ramp text
        card = _card(
            type_line="Sorcery",
            oracle_text="Search your library for a basic land card and put it onto the battlefield.",
        )
        features = extract_features(card, _COMMANDER)

        # is_ramp should be 1.0
        ramp_idx = FEATURE_NAMES.index("is_ramp")
        assert features[ramp_idx] == 1.0

        # is_board_wipe should be 0.0 (not a board wipe)
        wipe_idx = FEATURE_NAMES.index("is_board_wipe")
        assert features[wipe_idx] == 0.0

    def test_card_draw_category(self) -> None:
        """is_card_draw should be 1.0 for draw effects."""
        card = _card(
            type_line="Instant",
            oracle_text="Draw three cards.",
        )
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_card_draw")
        assert features[idx] == 1.0

    def test_removal_category(self) -> None:
        """is_removal should be 1.0 for removal effects."""
        card = _card(
            type_line="Instant",
            oracle_text="Destroy target creature.",
        )
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_removal")
        assert features[idx] == 1.0

    def test_protection_category(self) -> None:
        """is_protection should be 1.0 for protection effects."""
        card = _card(
            type_line="Instant",
            oracle_text="Target creature gains hexproof until end of turn.",
        )
        features = extract_features(card, _COMMANDER)
        idx = FEATURE_NAMES.index("is_protection")
        assert features[idx] == 1.0


class TestHelperFunctions:
    """Direct tests for helper functions."""

    def test_count_shared_keywords_empty(self) -> None:
        """No shared keywords when one card has none."""
        card = _card(keywords=[])
        commander = _card(name="Cmd", keywords=["Flying"])
        assert _count_shared_keywords(card, commander) == 0

    def test_has_type_positive(self) -> None:
        """_has_type returns 1.0 for matching type."""
        card = _card(type_line="Artifact Creature")
        assert _has_type(card, "Artifact") == 1.0

    def test_has_type_negative(self) -> None:
        """_has_type returns 0.0 for non-matching type."""
        card = _card(type_line="Instant")
        assert _has_type(card, "Creature") == 0.0

    def test_has_category_positive(self) -> None:
        """_has_category returns 1.0 when category present."""
        categories = [("ramp", 0.9), ("creature", 1.0)]
        assert _has_category(categories, "ramp") == 1.0

    def test_has_category_negative(self) -> None:
        """_has_category returns 0.0 when category absent."""
        categories = [("creature", 1.0)]
        assert _has_category(categories, "ramp") == 0.0

    def test_color_overlap_ratio_empty_card(self) -> None:
        """_color_overlap_ratio returns 0.0 when card has no colors."""
        card = _card(color_identity=[])
        commander = _card(name="Cmd", color_identity=["W"])
        assert _color_overlap_ratio(card, commander) == 0.0

    def test_tribal_match_no_types(self) -> None:
        """_tribal_match returns 0.0 when commander has no creature types."""
        card = _card(type_line="Creature \u2014 Elf")
        commander = _card(name="Cmd", type_line="Enchantment")
        assert _tribal_match(card, commander) == 0.0

    def test_theme_overlap_no_themes(self) -> None:
        """_theme_overlap returns 0.0 when commander has no themes."""
        card = _card(oracle_text="Create a token")
        commander = _card(name="Cmd", oracle_text="")
        assert _theme_overlap(card, commander) == 0.0

"""Tests for color identity utility functions."""

from __future__ import annotations

from mtg_deck_maker.utils.colors import (
    color_identity_to_name,
    is_within_identity,
    parse_color_identity,
    union_color_identities,
)


class TestParseColorIdentity:
    """Test parsing color identity from mana cost strings."""

    def test_empty_string(self) -> None:
        assert parse_color_identity("") == []

    def test_colorless_mana(self) -> None:
        assert parse_color_identity("{1}") == []

    def test_generic_mana(self) -> None:
        assert parse_color_identity("{3}") == []

    def test_single_color(self) -> None:
        assert parse_color_identity("{W}") == ["W"]

    def test_two_colors(self) -> None:
        result = parse_color_identity("{W}{U}")
        assert result == ["W", "U"]

    def test_multicolor_with_generic(self) -> None:
        result = parse_color_identity("{2}{W}{U}")
        assert result == ["W", "U"]

    def test_all_five_colors(self) -> None:
        result = parse_color_identity("{W}{U}{B}{R}{G}")
        assert result == ["W", "U", "B", "R", "G"]

    def test_hybrid_mana(self) -> None:
        result = parse_color_identity("{W/U}")
        assert result == ["W", "U"]

    def test_multiple_hybrid(self) -> None:
        result = parse_color_identity("{W/U}{B/G}")
        assert result == ["W", "U", "B", "G"]

    def test_duplicate_colors_deduped(self) -> None:
        result = parse_color_identity("{W}{W}{U}")
        assert result == ["W", "U"]

    def test_wubrg_order_preserved(self) -> None:
        result = parse_color_identity("{G}{R}{B}{U}{W}")
        assert result == ["W", "U", "B", "R", "G"]

    def test_colorless_symbol(self) -> None:
        result = parse_color_identity("{C}")
        assert result == []

    def test_x_cost(self) -> None:
        result = parse_color_identity("{X}{R}{R}")
        assert result == ["R"]

    def test_complex_mana_cost(self) -> None:
        # Atraxa: {G}{W}{U}{B}
        result = parse_color_identity("{G}{W}{U}{B}")
        assert result == ["W", "U", "B", "G"]


class TestUnionColorIdentities:
    """Test computing union of multiple color identities."""

    def test_empty_list(self) -> None:
        assert union_color_identities([]) == []

    def test_single_identity(self) -> None:
        result = union_color_identities([["W", "U"]])
        assert result == ["W", "U"]

    def test_two_disjoint_identities(self) -> None:
        result = union_color_identities([["W", "U"], ["B", "R"]])
        assert result == ["W", "U", "B", "R"]

    def test_overlapping_identities(self) -> None:
        result = union_color_identities([["W", "U"], ["U", "B"]])
        assert result == ["W", "U", "B"]

    def test_empty_identity_in_list(self) -> None:
        result = union_color_identities([[], ["R", "G"]])
        assert result == ["R", "G"]

    def test_all_empty(self) -> None:
        result = union_color_identities([[], []])
        assert result == []

    def test_full_wubrg_union(self) -> None:
        result = union_color_identities([["W"], ["U"], ["B"], ["R"], ["G"]])
        assert result == ["W", "U", "B", "R", "G"]


class TestIsWithinIdentity:
    """Test checking if card colors fit within commander identity."""

    def test_colorless_always_fits(self) -> None:
        assert is_within_identity([], ["W", "U"]) is True

    def test_colorless_fits_colorless(self) -> None:
        assert is_within_identity([], []) is True

    def test_exact_match(self) -> None:
        assert is_within_identity(["W", "U"], ["W", "U"]) is True

    def test_subset_fits(self) -> None:
        assert is_within_identity(["W"], ["W", "U", "B"]) is True

    def test_outside_identity(self) -> None:
        assert is_within_identity(["R"], ["W", "U"]) is False

    def test_partial_overlap_fails(self) -> None:
        assert is_within_identity(["W", "R"], ["W", "U"]) is False

    def test_full_wubrg_accepts_all(self) -> None:
        assert (
            is_within_identity(
                ["W", "U", "B", "R", "G"], ["W", "U", "B", "R", "G"]
            )
            is True
        )

    def test_colored_card_in_colorless_deck(self) -> None:
        assert is_within_identity(["W"], []) is False


class TestColorIdentityToName:
    """Test color identity to name conversion."""

    def test_colorless(self) -> None:
        assert color_identity_to_name([]) == "Colorless"

    def test_mono_colors(self) -> None:
        assert color_identity_to_name(["W"]) == "White"
        assert color_identity_to_name(["U"]) == "Blue"
        assert color_identity_to_name(["B"]) == "Black"
        assert color_identity_to_name(["R"]) == "Red"
        assert color_identity_to_name(["G"]) == "Green"

    def test_guilds(self) -> None:
        assert color_identity_to_name(["W", "U"]) == "Azorius"
        assert color_identity_to_name(["U", "B"]) == "Dimir"
        assert color_identity_to_name(["B", "R"]) == "Rakdos"
        assert color_identity_to_name(["R", "G"]) == "Gruul"
        assert color_identity_to_name(["U", "G"]) == "Simic"

    def test_shards_and_wedges(self) -> None:
        assert color_identity_to_name(["W", "U", "B"]) == "Esper"
        assert color_identity_to_name(["U", "B", "R"]) == "Grixis"
        assert color_identity_to_name(["B", "R", "G"]) == "Jund"

    def test_five_color(self) -> None:
        assert (
            color_identity_to_name(["W", "U", "B", "R", "G"]) == "Five-Color"
        )

    def test_unordered_input_sorted(self) -> None:
        # Should sort to WUBRG order before lookup
        assert color_identity_to_name(["G", "W"]) == "Selesnya"
        assert color_identity_to_name(["R", "W"]) == "Boros"



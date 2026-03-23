"""Tests for the output formatting utility helpers."""

from __future__ import annotations

import pytest

from mtg_deck_maker.utils.formatting import (
    format_color_identity,
    format_mana_cost,
    format_price,
)


# ===========================================================================
# format_price tests
# ===========================================================================


class TestFormatPrice:
    """Tests for format_price."""

    @pytest.mark.parametrize(
        "price, currency, expected",
        [
            (12.50, "USD", "$12.50"),
            (0.99, "USD", "$0.99"),
            (100.0, "USD", "$100.00"),
            (7.5, "EUR", "\u20ac7.50"),
            (0.01, "EUR", "\u20ac0.01"),
        ],
        ids=["usd_typical", "usd_cents", "usd_round", "eur_typical", "eur_small"],
    )
    def test_known_currencies(self, price: float, currency: str, expected: str) -> None:
        assert format_price(price, currency) == expected

    def test_unknown_currency_uses_code_prefix(self) -> None:
        # Unknown currency codes are used as a prefix with a trailing space
        result = format_price(5.00, "GBP")
        assert result == "GBP 5.00"

    def test_unknown_currency_non_standard(self) -> None:
        result = format_price(1.23, "JPY")
        assert result == "JPY 1.23"

    def test_zero_price(self) -> None:
        assert format_price(0.0, "USD") == "$0.00"

    def test_zero_price_eur(self) -> None:
        assert format_price(0.0, "EUR") == "\u20ac0.00"

    def test_negative_price(self) -> None:
        # Negative prices are formatted as-is (caller's responsibility)
        result = format_price(-3.50, "USD")
        assert result == "$-3.50"

    def test_decimal_rounding_two_places(self) -> None:
        # Python's :.2f rounds to 2 decimal places
        result = format_price(1.999, "USD")
        assert result == "$2.00"

    def test_large_price(self) -> None:
        result = format_price(9999.99, "USD")
        assert result == "$9999.99"

    def test_default_currency_is_usd(self) -> None:
        assert format_price(1.00) == "$1.00"


# ===========================================================================
# format_mana_cost tests
# ===========================================================================


class TestFormatManaCost:
    """Tests for format_mana_cost."""

    @pytest.mark.parametrize(
        "mana_cost",
        [
            "{1}{W}{U}{B}{G}",
            "{G}{G}",
            "{X}{R}",
            "{2}{W}",
            "{}",
            "",
        ],
        ids=[
            "five_color",
            "mono_green_double",
            "variable_red",
            "two_white",
            "empty_braces",
            "empty_string",
        ],
    )
    def test_passes_through_unchanged(self, mana_cost: str) -> None:
        """format_mana_cost passes the string through as-is."""
        assert format_mana_cost(mana_cost) == mana_cost

    def test_colorless_mana(self) -> None:
        assert format_mana_cost("{C}") == "{C}"

    def test_hybrid_mana(self) -> None:
        assert format_mana_cost("{W/U}{W/U}") == "{W/U}{W/U}"

    def test_phyrexian_mana(self) -> None:
        assert format_mana_cost("{W/P}") == "{W/P}"

    def test_returns_string_type(self) -> None:
        result = format_mana_cost("{G}")
        assert isinstance(result, str)


# ===========================================================================
# format_color_identity tests
# ===========================================================================


class TestFormatColorIdentity:
    """Tests for format_color_identity."""

    def test_empty_list_is_colorless(self) -> None:
        assert format_color_identity([]) == "Colorless"

    def test_single_color(self) -> None:
        assert format_color_identity(["G"]) == "G"

    def test_single_color_white(self) -> None:
        assert format_color_identity(["W"]) == "W"

    @pytest.mark.parametrize(
        "colors, expected",
        [
            (["W", "U"], "W,U"),
            (["U", "B"], "U,B"),
            (["B", "R"], "B,R"),
            (["R", "G"], "R,G"),
            (["W", "G"], "W,G"),
        ],
        ids=["WU", "UB", "BR", "RG", "WG"],
    )
    def test_two_color_combinations(self, colors: list[str], expected: str) -> None:
        assert format_color_identity(colors) == expected

    def test_three_colors(self) -> None:
        assert format_color_identity(["W", "U", "B"]) == "W,U,B"

    def test_four_colors(self) -> None:
        assert format_color_identity(["W", "U", "B", "G"]) == "W,U,B,G"

    def test_wubrg_five_color(self) -> None:
        # All five colors in WUBRG order
        assert format_color_identity(["W", "U", "B", "R", "G"]) == "W,U,B,R,G"

    def test_colors_joined_by_comma_no_space(self) -> None:
        result = format_color_identity(["R", "G"])
        assert " " not in result
        assert result == "R,G"

    def test_returns_string_type(self) -> None:
        assert isinstance(format_color_identity([]), str)
        assert isinstance(format_color_identity(["G"]), str)

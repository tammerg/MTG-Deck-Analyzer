"""Tests for the Deck and DeckCard data models."""

from __future__ import annotations

from mtg_deck_maker.models.deck import Deck, DeckCard


class TestDeckCard:
    """Test DeckCard dataclass."""

    def test_create_deck_card_defaults(self) -> None:
        card = DeckCard(card_id=1)
        assert card.card_id == 1
        assert card.quantity == 1
        assert card.category == ""
        assert card.is_commander is False
        assert card.is_companion is False
        assert card.card_name == ""
        assert card.cmc == 0.0
        assert card.colors == []
        assert card.price == 0.0

    def test_create_deck_card_full(self) -> None:
        card = DeckCard(
            card_id=42,
            quantity=1,
            category="Ramp",
            is_commander=False,
            is_companion=False,
            card_name="Sol Ring",
            cmc=1.0,
            colors=[],
            price=3.50,
        )
        assert card.card_name == "Sol Ring"
        assert card.price == 3.50
        assert card.category == "Ramp"


class TestDeckTotalCards:
    """Test Deck.total_cards() method."""

    def test_empty_deck(self) -> None:
        deck = Deck(name="Empty")
        assert deck.total_cards() == 0

    def test_singleton_deck(self) -> None:
        deck = Deck(
            name="Test",
            cards=[
                DeckCard(card_id=1, quantity=1),
                DeckCard(card_id=2, quantity=1),
                DeckCard(card_id=3, quantity=1),
            ],
        )
        assert deck.total_cards() == 3

    def test_full_commander_deck(self) -> None:
        cards = [DeckCard(card_id=i, quantity=1) for i in range(100)]
        cards[0].is_commander = True
        deck = Deck(name="Full", cards=cards)
        assert deck.total_cards() == 100


class TestDeckTotalPrice:
    """Test Deck.total_price() method."""

    def test_empty_deck_price(self) -> None:
        deck = Deck(name="Empty")
        assert deck.total_price() == 0.0

    def test_deck_price_calculation(self) -> None:
        deck = Deck(
            name="Priced",
            cards=[
                DeckCard(card_id=1, quantity=1, price=10.50),
                DeckCard(card_id=2, quantity=1, price=0.25),
                DeckCard(card_id=3, quantity=1, price=5.00),
            ],
        )
        assert deck.total_price() == 15.75

    def test_deck_price_with_quantity(self) -> None:
        deck = Deck(
            name="Multi",
            cards=[
                DeckCard(card_id=1, quantity=4, price=1.00),
                DeckCard(card_id=2, quantity=2, price=3.00),
            ],
        )
        assert deck.total_price() == 10.00


class TestDeckAverageCmc:
    """Test Deck.average_cmc() method."""

    def test_empty_deck_cmc(self) -> None:
        deck = Deck(name="Empty")
        assert deck.average_cmc() == 0.0

    def test_all_lands_cmc(self) -> None:
        deck = Deck(
            name="Lands",
            cards=[
                DeckCard(card_id=1, quantity=1, cmc=0.0),
                DeckCard(card_id=2, quantity=1, cmc=0.0),
            ],
        )
        assert deck.average_cmc() == 0.0

    def test_average_cmc_excludes_lands(self) -> None:
        deck = Deck(
            name="Mixed",
            cards=[
                DeckCard(card_id=1, quantity=1, cmc=0.0),   # Land
                DeckCard(card_id=2, quantity=1, cmc=1.0),   # Sol Ring
                DeckCard(card_id=3, quantity=1, cmc=3.0),   # 3-drop
                DeckCard(card_id=4, quantity=1, cmc=5.0),   # 5-drop
            ],
        )
        # Average of 1.0, 3.0, 5.0 = 3.0
        assert deck.average_cmc() == 3.0

    def test_average_cmc_with_quantities(self) -> None:
        deck = Deck(
            name="Quantities",
            cards=[
                DeckCard(card_id=1, quantity=2, cmc=2.0),
                DeckCard(card_id=2, quantity=1, cmc=4.0),
            ],
        )
        # (2*2.0 + 1*4.0) / (2+1) = 8.0/3 ≈ 2.667
        assert abs(deck.average_cmc() - 8.0 / 3) < 0.001


class TestDeckColorDistribution:
    """Test Deck.color_distribution() method."""

    def test_empty_deck_colors(self) -> None:
        deck = Deck(name="Empty")
        assert deck.color_distribution() == {}

    def test_colorless_cards(self) -> None:
        deck = Deck(
            name="Colorless",
            cards=[
                DeckCard(card_id=1, quantity=1, colors=[]),
                DeckCard(card_id=2, quantity=1, colors=[]),
            ],
        )
        assert deck.color_distribution() == {"": 2}

    def test_multicolor_distribution(self) -> None:
        deck = Deck(
            name="Multicolor",
            cards=[
                DeckCard(card_id=1, quantity=1, colors=["W"]),
                DeckCard(card_id=2, quantity=1, colors=["U"]),
                DeckCard(card_id=3, quantity=1, colors=["W", "U"]),
                DeckCard(card_id=4, quantity=1, colors=[]),
            ],
        )
        dist = deck.color_distribution()
        assert dist["W"] == 2  # Card 1 + Card 3
        assert dist["U"] == 2  # Card 2 + Card 3
        assert dist[""] == 1   # Card 4

    def test_color_distribution_with_quantities(self) -> None:
        deck = Deck(
            name="Quantities",
            cards=[
                DeckCard(card_id=1, quantity=3, colors=["R"]),
                DeckCard(card_id=2, quantity=2, colors=["R", "G"]),
            ],
        )
        dist = deck.color_distribution()
        assert dist["R"] == 5  # 3 + 2
        assert dist["G"] == 2


class TestDeckFilters:
    """Test Deck filtering methods."""

    def test_commanders(self) -> None:
        deck = Deck(
            name="Test",
            cards=[
                DeckCard(card_id=1, is_commander=True, card_name="Cmdr"),
                DeckCard(card_id=2, card_name="Card A"),
                DeckCard(card_id=3, card_name="Card B"),
            ],
        )
        commanders = deck.commanders()
        assert len(commanders) == 1
        assert commanders[0].card_name == "Cmdr"

    def test_companions(self) -> None:
        deck = Deck(
            name="Test",
            cards=[
                DeckCard(card_id=1, is_commander=True),
                DeckCard(card_id=2, is_companion=True, card_name="Comp"),
                DeckCard(card_id=3),
            ],
        )
        companions = deck.companions()
        assert len(companions) == 1
        assert companions[0].card_name == "Comp"

    def test_mainboard(self) -> None:
        deck = Deck(
            name="Test",
            cards=[
                DeckCard(card_id=1, is_commander=True),
                DeckCard(card_id=2, is_companion=True),
                DeckCard(card_id=3, card_name="Main A"),
                DeckCard(card_id=4, card_name="Main B"),
            ],
        )
        main = deck.mainboard()
        assert len(main) == 2
        assert main[0].card_name == "Main A"
        assert main[1].card_name == "Main B"

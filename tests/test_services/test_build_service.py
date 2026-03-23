"""Tests for the build service orchestration layer."""

from __future__ import annotations

import pytest

import logging

from unittest.mock import MagicMock, patch

from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.services.build_service import (
    BuildResult,
    BuildService,
    BuildServiceError,
    CommanderNotFoundError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(
    card_id: int,
    name: str,
    type_line: str = "Instant",
    oracle_text: str = "",
    mana_cost: str = "{1}",
    cmc: float = 1.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    keywords: list[str] | None = None,
    edhrec_rank: int = 1000,
    legal_commander: bool = True,
) -> Card:
    """Create a test Card with sensible defaults."""
    return Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=color_identity or [],
        keywords=keywords or [],
        edhrec_rank=edhrec_rank,
        legal_commander=legal_commander,
        id=card_id,
    )


def _build_mono_green_pool(size: int = 250) -> list[Card]:
    """Build a card pool for a mono-green commander."""
    pool: list[Card] = []
    card_id = 1

    # Ramp
    for j in range(15):
        pool.append(_make_card(
            card_id, f"Green Ramp {j}",
            "Sorcery", "Search your library for a Forest card.",
            "{1}{G}", 2.0, ["G"], ["G"], edhrec_rank=100 + j,
        ))
        card_id += 1

    # Colorless ramp
    for j in range(8):
        pool.append(_make_card(
            card_id, f"Mana Rock {j}",
            "Artifact", "{T}: Add {C}.",
            "{2}", 2.0, [], [], edhrec_rank=200 + j,
        ))
        card_id += 1

    # Draw
    for j in range(12):
        pool.append(_make_card(
            card_id, f"Green Draw {j}",
            "Sorcery", "Draw a card for each creature you control.",
            "{2}{G}", 3.0, ["G"], ["G"], edhrec_rank=300 + j,
        ))
        card_id += 1

    # Removal
    for j in range(10):
        pool.append(_make_card(
            card_id, f"Green Removal {j}",
            "Instant", "Destroy target artifact or enchantment.",
            "{1}{G}", 2.0, ["G"], ["G"], edhrec_rank=400 + j,
        ))
        card_id += 1

    # Board wipes
    for j in range(4):
        pool.append(_make_card(
            card_id, f"Green Wipe {j}",
            "Sorcery", "Destroy all artifacts and enchantments.",
            "{4}{G}", 5.0, ["G"], ["G"], edhrec_rank=500 + j,
        ))
        card_id += 1

    # Protection
    for j in range(6):
        pool.append(_make_card(
            card_id, f"Green Protection {j}",
            "Instant", "Target creature gains hexproof until end of turn.",
            "{G}", 1.0, ["G"], ["G"], edhrec_rank=600 + j,
        ))
        card_id += 1

    # Win conditions
    for j in range(10):
        pool.append(_make_card(
            card_id, f"Green Finisher {j}",
            "Creature - Beast", "Trample\nEach opponent loses life.",
            "{4}{G}{G}", 6.0, ["G"], ["G"],
            keywords=["Trample"],
            edhrec_rank=50 + j,
        ))
        card_id += 1

    # Creatures/utility
    while len(pool) < size:
        pool.append(_make_card(
            card_id, f"Green Creature {card_id}",
            "Creature - Elf", "When this enters, you gain 1 life.",
            "{2}{G}", 3.0, ["G"], ["G"], edhrec_rank=800 + card_id,
        ))
        card_id += 1

    # Basic lands
    pool.append(_make_card(
        card_id, "Forest", "Basic Land", "", "", 0.0, [], [],
        edhrec_rank=None,
    ))
    card_id += 1

    # Command Tower
    pool.append(_make_card(
        card_id, "Command Tower", "Land",
        "{T}: Add one mana of any color in your commander's color identity.",
        "", 0.0, [], [], edhrec_rank=2,
    ))
    card_id += 1

    return pool


def _build_mono_green_commander() -> Commander:
    """Create a mono-green commander."""
    cmd = _make_card(
        card_id=8000,
        name="Test Green Commander",
        type_line="Legendary Creature - Elf Druid",
        oracle_text="Whenever a land enters the battlefield under your control, you gain 1 life.",
        mana_cost="{2}{G}",
        cmc=3.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
        edhrec_rank=30,
    )
    return Commander(primary=cmd)


def _build_prices(pool: list[Card]) -> dict[int, float]:
    """Build a price dict for the pool."""
    prices: dict[int, float] = {}
    for card in pool:
        if card.id is not None:
            if card.is_land:
                prices[card.id] = 0.10
            elif card.edhrec_rank and card.edhrec_rank < 100:
                prices[card.id] = 2.00
            else:
                prices[card.id] = 0.50
    return prices


# ===========================================================================
# Tests
# ===========================================================================


class TestBuildService:
    """Tests for the BuildService class."""

    def test_end_to_end_build(self):
        """Service should produce a complete 100-card deck."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
        )

        assert isinstance(result, BuildResult)
        assert result.deck is not None
        assert result.deck.total_cards() == 100
        assert hasattr(result, "warnings")
        assert isinstance(result.warnings, list)

    def test_build_with_csv_export(self):
        """Service should produce CSV output when requested."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
            export_csv=True,
        )

        assert result.csv_output is not None
        assert "Card Name" in result.csv_output
        assert "DECK SUMMARY" in result.csv_output

    def test_invalid_commander_raises_service_error(self):
        """Service should raise BuildServiceError for invalid commander."""
        service = BuildService()
        bad_card = _make_card(
            9999, "Not A Legend",
            "Creature - Human", "", "{1}", 1.0, [], [],
        )
        commander = Commander(primary=bad_card)
        pool = _build_mono_green_pool()

        with pytest.raises(BuildServiceError, match="Commander validation failed"):
            service.build(
                commander=commander,
                budget=100.0,
                card_pool=pool,
            )

    def test_deterministic_builds(self):
        """Same seed should produce identical results."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result1 = service.build(
            commander=commander, budget=150.0,
            card_pool=pool, prices=prices, seed=42,
        )
        result2 = service.build(
            commander=commander, budget=150.0,
            card_pool=pool, prices=prices, seed=42,
        )

        names1 = sorted(c.card_name for c in result1.deck.cards)
        names2 = sorted(c.card_name for c in result2.deck.cards)
        assert names1 == names2


class TestBuildFromDb:
    """Tests for the build_from_db() orchestration method."""

    def _setup_mock_db(
        self, commander_name: str = "Test Green Commander",
        partner_name: str | None = None,
    ) -> MagicMock:
        """Create a mock DB with card_repo and price_repo wired up."""
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)
        commander_card = _build_mono_green_commander().primary

        mock_db = MagicMock()

        def get_card_by_name(name: str):
            if name == commander_name:
                return commander_card
            if partner_name and name == partner_name:
                return _make_card(
                    8001, partner_name,
                    "Legendary Creature - Elf",
                    "", "{1}{G}", 2.0, ["G"], ["G"],
                )
            return None

        mock_card_repo = MagicMock()
        mock_card_repo.get_card_by_name.side_effect = get_card_by_name
        mock_card_repo.search_cards.return_value = []
        mock_card_repo.get_cards_by_color_identity.return_value = pool

        mock_price_repo = MagicMock()
        mock_price_repo.get_cheapest_prices.return_value = prices

        return mock_db, mock_card_repo, mock_price_repo

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_happy_path(self, MockPriceRepo, MockCardRepo):
        mock_db, mock_card_repo, mock_price_repo = self._setup_mock_db()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        service = BuildService()
        result = service.build_from_db(
            commander_name="Test Green Commander",
            budget=150.0,
            db=mock_db,
        )

        assert isinstance(result, BuildResult)
        assert result.deck is not None
        assert result.deck.total_cards() == 100

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_commander_not_found(self, MockPriceRepo, MockCardRepo):
        mock_db = MagicMock()
        mock_card_repo = MagicMock()
        mock_card_repo.get_card_by_name.return_value = None
        mock_card_repo.search_cards.return_value = []
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = MagicMock()

        service = BuildService()
        with pytest.raises(CommanderNotFoundError, match="not found"):
            service.build_from_db(
                commander_name="Nonexistent Commander",
                budget=100.0,
                db=mock_db,
            )

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_commander_not_found_with_suggestions(self, MockPriceRepo, MockCardRepo):
        mock_db = MagicMock()
        mock_card_repo = MagicMock()
        mock_card_repo.get_card_by_name.return_value = None
        suggestion = _make_card(1, "Similar Commander", "Legendary Creature")
        mock_card_repo.search_cards.return_value = [suggestion]
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = MagicMock()

        service = BuildService()
        with pytest.raises(CommanderNotFoundError, match="Did you mean"):
            service.build_from_db(
                commander_name="Nonexistent",
                budget=100.0,
                db=mock_db,
            )

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_partner_not_found(self, MockPriceRepo, MockCardRepo):
        mock_db, mock_card_repo, mock_price_repo = self._setup_mock_db()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        service = BuildService()
        with pytest.raises(CommanderNotFoundError, match="Partner"):
            service.build_from_db(
                commander_name="Test Green Commander",
                budget=100.0,
                db=mock_db,
                partner_name="Nonexistent Partner",
            )

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_ml_predictor_failure_logged_at_debug(self, MockPriceRepo, MockCardRepo):
        """A failing ML predictor import should be logged at DEBUG, not silenced."""
        mock_db, mock_card_repo, mock_price_repo = self._setup_mock_db()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        service = BuildService()
        # Verify that _load_ml_predictor catches and logs at DEBUG (not WARNING)
        # by triggering an ImportError inside the method.
        with patch("mtg_deck_maker.services.build_service.logger") as mock_logger:
            # Patch builtins.__import__ won't work cleanly; patch the lazy import
            # by making PowerPredictor itself raise on instantiation.
            with patch(
                "mtg_deck_maker.ml.predictor.PowerPredictor",
                side_effect=ImportError("no module named mtg_deck_maker.ml"),
            ):
                result = service.build_from_db(
                    commander_name="Test Green Commander",
                    budget=150.0,
                    db=mock_db,
                )

        # Build should succeed regardless of ML predictor failure
        assert result.deck.total_cards() == 100
        # debug should have been called with the ML predictor message
        debug_calls = [str(c) for c in mock_logger.debug.call_args_list]
        assert any("ML predictor" in c for c in debug_calls)


class TestBuildServiceHelpers:
    """Unit tests for the extracted private helper methods."""

    def test_load_ml_predictor_returns_none_when_unavailable(self):
        """_load_ml_predictor should return None gracefully when ML is absent."""
        service = BuildService()
        with patch(
            "mtg_deck_maker.ml.predictor.PowerPredictor",
            side_effect=ImportError("missing"),
        ):
            result = service._load_ml_predictor()
        assert result is None

    def test_load_ml_predictor_returns_none_when_not_available(self):
        """Returns None when PowerPredictor.is_available() is False."""
        service = BuildService()
        mock_pp = MagicMock()
        mock_pp.is_available.return_value = False
        with patch("mtg_deck_maker.ml.predictor.PowerPredictor", return_value=mock_pp):
            result = service._load_ml_predictor()
        assert result is None

    def test_load_ml_predictor_returns_predictor_when_available(self):
        """Returns the predictor instance when is_available() is True."""
        service = BuildService()
        mock_pp = MagicMock()
        mock_pp.is_available.return_value = True
        with patch("mtg_deck_maker.ml.predictor.PowerPredictor", return_value=mock_pp):
            result = service._load_ml_predictor()
        assert result is mock_pp

    def test_run_smart_research_returns_none_when_no_provider(self):
        """Returns None gracefully when no LLM provider is configured."""
        service = BuildService()
        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            return_value=None,
        ):
            result = service._run_smart_research(
                cmd_name="Test Commander",
                budget=100.0,
                oracle_text="",
                color_identity=["G"],
                llm_provider="auto",
                llm_model=None,
            )
        assert result is None

    def test_fetch_edhrec_data_returns_none_on_exception(self):
        """Returns None when EDHREC raises an exception."""
        service = BuildService()
        mock_db = MagicMock()
        with patch(
            "mtg_deck_maker.db.edhrec_repo.EdhrecRepository",
            side_effect=Exception("network error"),
        ):
            result = service._fetch_edhrec_data("Test Commander", mock_db)
        assert result is None

    def test_fetch_edhrec_data_returns_dict_on_success(self):
        """Returns a card-name -> inclusion-rate dict when data is available."""
        service = BuildService()
        mock_db = MagicMock()

        # Mock repo that reports data is present and not stale
        mock_repo = MagicMock()
        mock_repo.has_data.return_value = True
        mock_repo.is_stale.return_value = False

        # Two top cards returned
        card_a = MagicMock()
        card_a.card_name = "Sol Ring"
        card_a.inclusion_rate = 0.95

        card_b = MagicMock()
        card_b.card_name = "Command Tower"
        card_b.inclusion_rate = 0.90

        mock_repo.get_top_cards.return_value = [card_a, card_b]

        with patch("mtg_deck_maker.db.edhrec_repo.EdhrecRepository", return_value=mock_repo):
            result = service._fetch_edhrec_data("Test Commander", mock_db)

        assert result is not None
        assert result["Sol Ring"] == pytest.approx(0.95)
        assert result["Command Tower"] == pytest.approx(0.90)

    def test_fetch_edhrec_data_logs_warning_on_failure(self, caplog):
        """A warning is logged when EDHREC data cannot be fetched."""
        service = BuildService()
        mock_db = MagicMock()

        with patch(
            "mtg_deck_maker.db.edhrec_repo.EdhrecRepository",
            side_effect=RuntimeError("timeout"),
        ):
            with caplog.at_level(logging.WARNING, logger="mtg_deck_maker.services.build_service"):
                result = service._fetch_edhrec_data("Test Commander", mock_db)

        assert result is None
        assert any("EDHREC" in r.message for r in caplog.records)

    def test_run_smart_research_returns_key_cards_on_success(self):
        """Returns the list of key cards when research succeeds."""
        service = BuildService()

        mock_llm = MagicMock()
        mock_llm.name = "test-provider"

        mock_research = MagicMock()
        mock_research.parse_success = True
        mock_research.key_cards = ["Sol Ring", "Command Tower", "Arcane Signet"]

        mock_research_svc = MagicMock()
        mock_research_svc.research_commander.return_value = mock_research

        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            return_value=mock_llm,
        ):
            with patch(
                "mtg_deck_maker.services.research_service.ResearchService",
                return_value=mock_research_svc,
            ):
                result = service._run_smart_research(
                    cmd_name="Test Commander",
                    budget=150.0,
                    oracle_text="Proliferate at end of turn.",
                    color_identity=["W", "U", "B", "G"],
                    llm_provider="auto",
                    llm_model=None,
                )

        assert result == ["Sol Ring", "Command Tower", "Arcane Signet"]

    def test_run_smart_research_returns_none_on_parse_failure(self, caplog):
        """Returns None and logs a warning when LLM response cannot be parsed."""
        service = BuildService()

        mock_llm = MagicMock()
        mock_llm.name = "test-provider"

        mock_research = MagicMock()
        mock_research.parse_success = False
        mock_research.key_cards = []

        mock_research_svc = MagicMock()
        mock_research_svc.research_commander.return_value = mock_research

        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            return_value=mock_llm,
        ):
            with patch(
                "mtg_deck_maker.services.research_service.ResearchService",
                return_value=mock_research_svc,
            ):
                with caplog.at_level(
                    logging.WARNING, logger="mtg_deck_maker.services.build_service"
                ):
                    result = service._run_smart_research(
                        cmd_name="Test Commander",
                        budget=150.0,
                        oracle_text="",
                        color_identity=["G"],
                        llm_provider="auto",
                        llm_model=None,
                    )

        assert result is None
        assert any("could not be parsed" in r.message for r in caplog.records)

    def test_run_smart_research_returns_none_on_exception(self, caplog):
        """Returns None and logs a warning when an unexpected exception occurs."""
        service = BuildService()

        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            side_effect=RuntimeError("LLM connection refused"),
        ):
            with caplog.at_level(
                logging.WARNING, logger="mtg_deck_maker.services.build_service"
            ):
                result = service._run_smart_research(
                    cmd_name="Test Commander",
                    budget=100.0,
                    oracle_text="",
                    color_identity=["G"],
                    llm_provider="auto",
                    llm_model=None,
                )

        assert result is None
        assert any("Smart build research failed" in r.message for r in caplog.records)

    def test_generate_llm_synergy_matrix_returns_cached_matrix(self):
        """Returns the cached matrix when it already exists in the repo."""
        service = BuildService()
        mock_db = MagicMock()
        cmd_card = _make_card(1, "Atraxa", "Legendary Creature", color_identity=["W", "U", "B", "G"])
        pool = [_make_card(i, f"Card {i}", color_identity=["G"]) for i in range(2, 20)]

        cached_matrix = {("Atraxa", "Sol Ring"): 0.8, ("Atraxa", "Command Tower"): 0.7}

        mock_llm = MagicMock()
        mock_llm.model_id = "claude-3-opus"

        mock_repo = MagicMock()
        mock_repo.get_cached_matrix.return_value = cached_matrix

        with patch("mtg_deck_maker.advisor.llm_provider.get_provider", return_value=mock_llm):
            with patch(
                "mtg_deck_maker.db.llm_synergy_repo.LLMSynergyRepo",
                return_value=mock_repo,
            ):
                result = service._generate_llm_synergy_matrix(
                    commander_name="Atraxa",
                    cmd_card=cmd_card,
                    card_pool=pool,
                    llm_provider="auto",
                    llm_model=None,
                    db=mock_db,
                )

        assert result == cached_matrix

    def test_generate_llm_synergy_matrix_returns_none_on_no_provider(self):
        """Returns None immediately when no LLM provider is configured."""
        service = BuildService()
        mock_db = MagicMock()
        cmd_card = _make_card(1, "Atraxa", "Legendary Creature")
        pool = [_make_card(i, f"Card {i}") for i in range(2, 10)]

        with patch("mtg_deck_maker.advisor.llm_provider.get_provider", return_value=None):
            result = service._generate_llm_synergy_matrix(
                commander_name="Atraxa",
                cmd_card=cmd_card,
                card_pool=pool,
                llm_provider="auto",
                llm_model=None,
                db=mock_db,
            )

        assert result is None

    def test_generate_llm_synergy_matrix_returns_none_on_failure(self, caplog):
        """Returns None and logs a warning when matrix generation raises."""
        service = BuildService()
        mock_db = MagicMock()
        cmd_card = _make_card(1, "Atraxa", "Legendary Creature")
        pool = [_make_card(i, f"Card {i}") for i in range(2, 10)]

        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            side_effect=RuntimeError("API error"),
        ):
            with caplog.at_level(
                logging.WARNING, logger="mtg_deck_maker.services.build_service"
            ):
                result = service._generate_llm_synergy_matrix(
                    commander_name="Atraxa",
                    cmd_card=cmd_card,
                    card_pool=pool,
                    llm_provider="auto",
                    llm_model=None,
                    db=mock_db,
                )

        assert result is None
        assert any("synergy matrix failed" in r.message for r in caplog.records)


# ===========================================================================
# build_from_db full orchestration tests
# ===========================================================================


class TestBuildFromDbOrchestration:
    """Tests for the full build_from_db orchestration path."""

    def _make_mock_db_setup(
        self, commander_name: str = "Test Green Commander"
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Return (mock_db, mock_card_repo, mock_price_repo) wired up."""
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)
        commander_card = _build_mono_green_commander().primary

        mock_db = MagicMock()

        mock_card_repo = MagicMock()
        mock_card_repo.get_card_by_name.side_effect = (
            lambda name: commander_card if name == commander_name else None
        )
        mock_card_repo.search_cards.return_value = []
        mock_card_repo.get_cards_by_color_identity.return_value = pool

        mock_price_repo = MagicMock()
        mock_price_repo.get_cheapest_prices.return_value = prices

        return mock_db, mock_card_repo, mock_price_repo

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_build_from_db_with_no_edhrec(self, MockPriceRepo, MockCardRepo):
        """build_from_db with no_edhrec=True should skip EDHREC fetch."""
        mock_db, mock_card_repo, mock_price_repo = self._make_mock_db_setup()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        service = BuildService()
        service._fetch_edhrec_data = MagicMock(return_value=None)

        result = service.build_from_db(
            commander_name="Test Green Commander",
            budget=150.0,
            db=mock_db,
            no_edhrec=True,
        )

        # _fetch_edhrec_data must not have been called
        service._fetch_edhrec_data.assert_not_called()
        assert result.deck.total_cards() == 100

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_build_from_db_progress_callback_called(self, MockPriceRepo, MockCardRepo):
        """Progress callback should receive status messages during the build."""
        mock_db, mock_card_repo, mock_price_repo = self._make_mock_db_setup()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        messages: list[str] = []
        service = BuildService()
        result = service.build_from_db(
            commander_name="Test Green Commander",
            budget=150.0,
            db=mock_db,
            no_edhrec=True,
            progress_callback=messages.append,
        )

        assert result.deck.total_cards() == 100
        assert len(messages) > 0
        assert any("commander" in m.lower() for m in messages)

    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    def test_build_from_db_smart_skips_synergy_when_no_priority_cards(
        self, MockPriceRepo, MockCardRepo
    ):
        """LLM synergy matrix should not be generated when smart research returns None."""
        mock_db, mock_card_repo, mock_price_repo = self._make_mock_db_setup()
        MockCardRepo.return_value = mock_card_repo
        MockPriceRepo.return_value = mock_price_repo

        service = BuildService()
        service._run_smart_research = MagicMock(return_value=None)
        service._generate_llm_synergy_matrix = MagicMock(return_value=None)

        result = service.build_from_db(
            commander_name="Test Green Commander",
            budget=150.0,
            db=mock_db,
            no_edhrec=True,
            smart=True,
        )

        service._run_smart_research.assert_called_once()
        service._generate_llm_synergy_matrix.assert_not_called()
        assert result.deck.total_cards() == 100

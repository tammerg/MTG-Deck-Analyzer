"""Build service orchestrating commander deck construction end-to-end.

Provides a high-level API that coordinates the deck builder, budget optimizer,
and CSV export to produce a complete Commander deck from input parameters.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from mtg_deck_maker.config import AppConfig

if TYPE_CHECKING:
    from mtg_deck_maker.db.database import Database
from mtg_deck_maker.engine.deck_builder import DeckBuildError, build_deck
from mtg_deck_maker.io.csv_export import export_deck_to_csv
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.models.deck import Deck

logger = logging.getLogger(__name__)


class BuildServiceError(Exception):
    """Raised when the build service encounters an error."""


class CommanderNotFoundError(BuildServiceError):
    """Commander or partner not found in database."""


class BuildResult:
    """Result of a deck build operation.

    Attributes:
        deck: The constructed Deck object.
        warnings: List of non-fatal warning messages.
        csv_output: Optional CSV string representation of the deck.
    """

    __slots__ = ("deck", "warnings", "csv_output")

    def __init__(
        self,
        deck: Deck,
        warnings: list[str] | None = None,
        csv_output: str | None = None,
    ) -> None:
        self.deck = deck
        self.warnings = warnings or []
        self.csv_output = csv_output


class BuildService:
    """Service orchestrating the full deck build pipeline.

    Coordinates: load commander -> build deck -> validate -> export.

    Attributes:
        config: Application configuration.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        """Initialize the build service.

        Args:
            config: Application configuration. Uses defaults if None.
        """
        self.config = config or AppConfig()

    def build(
        self,
        commander: Commander,
        budget: float,
        card_pool: list[Card],
        prices: dict[int, float] | None = None,
        seed: int = 42,
        export_csv: bool = False,
        csv_filepath: str | None = None,
        priority_cards: list[str] | None = None,
        edhrec_inclusion: dict[str, float] | None = None,
        llm_synergy_matrix: dict[tuple[str, str], float] | None = None,
        power_predictor: object | None = None,
    ) -> BuildResult:
        """Execute the full deck build pipeline.

        Steps:
            1. Validate the commander configuration.
            2. Build the deck using the deck builder engine.
            3. Optionally export to CSV.

        Args:
            commander: Commander configuration to build around.
            budget: Total deck budget in USD.
            card_pool: Available cards to select from.
            prices: Optional card_id -> price mapping.
            seed: Random seed for deterministic output.
            export_csv: Whether to generate CSV output.
            csv_filepath: File path to write CSV (if export_csv is True).
            priority_cards: Optional list of card names recommended by LLM.
            edhrec_inclusion: Optional per-commander card inclusion rates
                mapping card name -> inclusion rate (0.0 to 1.0).
            power_predictor: Optional ML power predictor for card scoring.

        Returns:
            BuildResult containing the deck, warnings, and optional CSV.

        Raises:
            BuildServiceError: If the build fails critically.
        """
        warnings: list[str] = []

        # Step 1: Pre-validate commander
        validation_errors = commander.validate()
        if validation_errors:
            raise BuildServiceError(
                f"Commander validation failed: {'; '.join(validation_errors)}"
            )

        # Step 2: Build the deck
        try:
            deck = build_deck(
                commander=commander,
                budget=budget,
                card_pool=card_pool,
                config=self.config,
                prices=prices,
                seed=seed,
                priority_cards=priority_cards,
                edhrec_inclusion=edhrec_inclusion,
                llm_synergy_matrix=llm_synergy_matrix,
                power_predictor=power_predictor,
            )
        except DeckBuildError as exc:
            raise BuildServiceError(f"Deck build failed: {exc}") from exc

        # Collect any post-build warnings
        total = deck.total_cards()
        if total != 100:
            warnings.append(
                f"Deck has {total} cards instead of the expected 100."
            )

        total_price = deck.total_price()
        if total_price > budget * 1.05:
            warnings.append(
                f"Deck cost ${total_price:.2f} exceeds budget "
                f"${budget:.2f} with 5% tolerance."
            )
        elif total_price > budget:
            warnings.append(
                f"Deck cost ${total_price:.2f} is slightly over budget "
                f"${budget:.2f} but within 5% tolerance."
            )

        # Step 3: Optional CSV export
        csv_output = None
        if export_csv:
            csv_output = export_deck_to_csv(
                deck=deck,
                filepath=csv_filepath,
            )

        return BuildResult(
            deck=deck,
            warnings=warnings,
            csv_output=csv_output,
        )

    def build_from_db(
        self,
        commander_name: str,
        budget: float,
        db: Database,
        *,
        partner_name: str | None = None,
        seed: int = 42,
        smart: bool = False,
        provider: str = "auto",
        llm_model: str | None = None,
        no_edhrec: bool = False,
        export_csv: bool = False,
        csv_filepath: str | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> BuildResult:
        """Execute the full build pipeline using the card database.

        Consolidates the build orchestration that was duplicated between
        the CLI and web API.  Steps:
            1. Look up commander (and optional partner) in the DB.
            2. Build Commander model.
            3. Load card pool by color identity.
            4. Load prices in bulk.
            5. Fetch EDHREC per-commander data (unless disabled).
            6. Run smart LLM research (if requested).
            7. Delegate to ``self.build()`` with all gathered data.

        Args:
            commander_name: Exact name of the commander card.
            budget: Total deck budget in USD.
            db: A ``Database`` instance (open connection).
            partner_name: Optional partner commander name.
            seed: Random seed for reproducibility.
            smart: Whether to run LLM-assisted research.
            provider: LLM provider selector ("auto", "openai", "anthropic").
            llm_model: Optional LLM model override.
            no_edhrec: Skip EDHREC data fetching.
            export_csv: Whether to generate CSV output.
            csv_filepath: File path for CSV export.
            progress_callback: Optional callable receiving status messages.

        Returns:
            BuildResult with the constructed deck.

        Raises:
            CommanderNotFoundError: If commander or partner is not in the DB.
            BuildServiceError: If the build fails.
        """
        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.price_repo import PriceRepository

        def _progress(msg: str) -> None:
            if progress_callback is not None:
                progress_callback(msg)

        card_repo = CardRepository(db)
        price_repo = PriceRepository(db)

        # 1. Look up commander
        _progress("Looking up commander...")
        cmd_card = card_repo.get_card_by_name(commander_name)
        if cmd_card is None:
            suggestions = card_repo.search_cards(commander_name)
            hint = ""
            if suggestions:
                names = [c.name for c in suggestions[:5]]
                hint = f" Did you mean: {', '.join(names)}?"
            raise CommanderNotFoundError(
                f"Commander '{commander_name}' not found in database.{hint}"
            )

        # 2. Optional partner
        partner_card = None
        if partner_name:
            partner_card = card_repo.get_card_by_name(partner_name)
            if partner_card is None:
                raise CommanderNotFoundError(
                    f"Partner '{partner_name}' not found in database."
                )

        cmd = Commander(primary=cmd_card, partner=partner_card)
        color_identity = cmd.combined_color_identity()

        # 3. Card pool
        _progress(
            f"Loading card pool for {'/'.join(color_identity) or 'colorless'}..."
        )
        card_pool = card_repo.get_cards_by_color_identity(color_identity)
        _progress(f"Found {len(card_pool)} candidates")

        # 4. Bulk prices
        _progress("Loading prices...")
        card_ids = [c.id for c in card_pool if c.id is not None]
        if cmd_card.id is not None:
            card_ids.append(cmd_card.id)
        if partner_card is not None and partner_card.id is not None:
            card_ids.append(partner_card.id)
        prices = price_repo.get_cheapest_prices(card_ids)

        # 5. EDHREC per-commander data
        edhrec_inclusion: dict[str, float] | None = None
        if not no_edhrec:
            try:
                from mtg_deck_maker.api.edhrec import fetch_commander_data
                from mtg_deck_maker.db.edhrec_repo import EdhrecRepository

                edhrec_repo = EdhrecRepository(db)
                edhrec_repo.create_tables()

                cmd_name = cmd_card.name
                if not edhrec_repo.has_data(cmd_name) or edhrec_repo.is_stale(cmd_name):
                    _progress("Fetching EDHREC data...")
                    import asyncio

                    edhrec_data = asyncio.run(fetch_commander_data(cmd_name))
                    if edhrec_data:
                        edhrec_repo.upsert_data(edhrec_data)
                        _progress(f"Cached {len(edhrec_data)} EDHREC cards for {cmd_name}")

                if edhrec_repo.has_data(cmd_name):
                    top_cards = edhrec_repo.get_top_cards(cmd_name, limit=500)
                    edhrec_inclusion = {
                        c.card_name: c.inclusion_rate for c in top_cards
                    }
                    _progress(f"Using {len(edhrec_inclusion)} EDHREC card ratings")
            except Exception as exc:
                logger.warning("EDHREC data unavailable: %s", exc)
                _progress(f"EDHREC data unavailable: {exc}")

        # 6. Smart research
        priority_cards: list[str] | None = None
        if smart:
            try:
                from mtg_deck_maker.advisor.llm_provider import get_provider
                from mtg_deck_maker.services.research_service import ResearchService

                llm = get_provider(provider, model=llm_model)
                if llm is None:
                    _progress("No LLM provider available, skipping smart research")
                else:
                    _progress(f"Researching {commander_name} via {llm.name}...")
                    research_svc = ResearchService(provider=llm)
                    research = research_svc.research_commander(
                        commander_name=commander_name,
                        oracle_text=cmd_card.oracle_text,
                        color_identity=color_identity,
                        budget=budget,
                    )
                    if research.parse_success and research.key_cards:
                        priority_cards = research.key_cards
                        _progress(
                            f"LLM recommended {len(priority_cards)} priority cards"
                        )
                    elif not research.parse_success:
                        _progress("LLM response could not be parsed")
            except Exception as exc:
                logger.warning("Smart build research failed: %s", exc)
                _progress(f"Smart build research failed: {exc}")

        # 6b. LLM synergy matrix (when smart mode + LLM available)
        llm_synergy_matrix: dict[tuple[str, str], float] | None = None
        if smart and priority_cards:
            try:
                from mtg_deck_maker.advisor.llm_provider import get_provider as _get_provider
                from mtg_deck_maker.advisor.llm_synergy import (
                    generate_synergy_matrix,
                )
                from mtg_deck_maker.db.llm_synergy_repo import LLMSynergyRepo

                llm = _get_provider(provider, model=llm_model)
                if llm is not None:
                    synergy_repo = LLMSynergyRepo(db)
                    synergy_repo.create_tables()

                    model_name = llm_model or llm.name
                    card_names = [c.name for c in card_pool[:100]]
                    cached = synergy_repo.get_cached_matrix(
                        commander_name, card_names, model_name,
                    )
                    if cached:
                        llm_synergy_matrix = cached
                        _progress(
                            f"Using {len(cached)} cached LLM synergy scores"
                        )
                    else:
                        _progress("Generating LLM synergy matrix...")
                        llm_synergy_matrix = generate_synergy_matrix(
                            cmd_card,
                            card_pool[:100],
                            llm,
                            top_n=100,
                            batch_size=50,
                        )
                        if llm_synergy_matrix:
                            synergy_repo.upsert_scores(
                                commander_name,
                                llm_synergy_matrix,
                                model_name,
                            )
                            _progress(
                                f"Cached {len(llm_synergy_matrix)} LLM synergy scores"
                            )
            except Exception as exc:
                logger.warning("LLM synergy matrix failed: %s", exc)
                _progress(f"LLM synergy matrix unavailable: {exc}")

        # 6c. ML power predictor (auto-load if model file exists)
        predictor: object | None = None
        try:
            from mtg_deck_maker.ml.predictor import PowerPredictor

            pp = PowerPredictor()
            if pp.is_available():
                predictor = pp
                _progress("Using ML power prediction model")
        except Exception:
            pass

        # 7. Build
        _progress("Building deck...")
        return self.build(
            commander=cmd,
            budget=budget,
            card_pool=card_pool,
            prices=prices,
            seed=seed,
            export_csv=export_csv,
            csv_filepath=csv_filepath,
            priority_cards=priority_cards,
            edhrec_inclusion=edhrec_inclusion,
            llm_synergy_matrix=llm_synergy_matrix,
            power_predictor=predictor,
        )

"""Build service orchestrating commander deck construction end-to-end.

Provides a high-level API that coordinates the deck builder, budget optimizer,
and CSV export to produce a complete Commander deck from input parameters.
"""

from __future__ import annotations

from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.engine.deck_builder import DeckBuildError, build_deck
from mtg_deck_maker.io.csv_export import export_deck_to_csv
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.models.deck import Deck


class BuildServiceError(Exception):
    """Raised when the build service encounters an error."""


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

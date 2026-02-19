"""Click CLI entry point for the MTG Deck Maker application."""

from __future__ import annotations

import os
import sys

import click

from mtg_deck_maker import __version__


@click.group()
@click.version_option(version=__version__, prog_name="mtg-deck")
def cli() -> None:
    """MTG Commander Deck Creator - build, analyze, and upgrade Commander decks."""


@cli.command()
@click.argument("commander")
@click.option("--budget", type=float, default=100.0, help="Target budget in USD.")
@click.option("--output", "-o", type=click.Path(), help="Output CSV path.")
@click.option("--partner", type=str, help="Partner commander name.")
@click.option("--power-level", type=int, help="Target power level (1-10).")
@click.option("--config", "config_file", type=click.Path(), help="Config file path.")
@click.option("--seed", type=int, default=42, help="Random seed for reproducibility.")
def build(
    commander: str,
    budget: float,
    output: str | None,
    partner: str | None,
    power_level: int | None,
    config_file: str | None,
    seed: int,
) -> None:
    """Generate a Commander deck for the given commander.

    COMMANDER is the name of the commander card to build around.
    """
    try:
        from rich.console import Console

        console = Console()
        console.print(
            f"[bold]Building deck for:[/bold] {commander}", highlight=False
        )
        console.print(f"[dim]Budget:[/dim] ${budget:.2f}")
        if partner:
            console.print(f"[dim]Partner:[/dim] {partner}")
        if power_level:
            console.print(f"[dim]Target Power Level:[/dim] {power_level}")
        console.print(f"[dim]Seed:[/dim] {seed}")
        console.print()

        # The build command requires a card database and card pool.
        # Until the full Scryfall sync is implemented, provide guidance.
        console.print(
            "[yellow]Note:[/yellow] The build command requires a synced "
            "card database. Run 'mtg-deck sync --full' first to download "
            "card data.",
            highlight=False,
        )
    except ImportError:
        click.echo(f"Building deck for: {commander}")
        click.echo(f"Budget: ${budget:.2f}")
        click.echo(
            "Note: The build command requires a synced card database. "
            "Run 'mtg-deck sync --full' first."
        )


@cli.command()
@click.argument("deck_file", type=click.Path(exists=True))
def analyze(deck_file: str) -> None:
    """Analyze an existing deck from a CSV file.

    DECK_FILE is the path to a CSV/text deck list file.
    """
    try:
        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.services.analyze_service import AnalyzeService

        console = Console()
        service = AnalyzeService()

        console.print(f"[bold]Analyzing:[/bold] {deck_file}", highlight=False)
        console.print()

        analysis = service.analyze_from_csv(deck_file)

        # Category breakdown table
        table = Table(title="Category Breakdown")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")

        for cat, count in sorted(
            analysis.category_breakdown.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            table.add_row(cat, str(count))

        console.print(table)
        console.print()

        # Mana curve
        curve_table = Table(title="Mana Curve")
        curve_table.add_column("CMC", style="cyan")
        curve_table.add_column("Count", justify="right", style="green")
        curve_table.add_column("Bar", style="blue")

        for cmc_val in sorted(analysis.mana_curve.keys()):
            count = analysis.mana_curve[cmc_val]
            label = f"{cmc_val}+" if cmc_val == 7 else str(cmc_val)
            bar = "#" * count
            curve_table.add_row(label, str(count), bar)

        console.print(curve_table)
        console.print()

        # Summary stats
        console.print(f"[bold]Average CMC:[/bold] {analysis.avg_cmc:.2f}")
        console.print(f"[bold]Power Level:[/bold] {analysis.power_level}/10")
        console.print(
            f"[bold]Total Price:[/bold] ${analysis.total_price:.2f}"
        )
        console.print()

        # Weak/strong categories
        if analysis.weak_categories:
            console.print("[bold red]Weak Areas:[/bold red]")
            for cat in analysis.weak_categories:
                console.print(f"  - {cat}", highlight=False)
            console.print()

        if analysis.strong_categories:
            console.print("[bold green]Strong Areas:[/bold green]")
            for cat in analysis.strong_categories:
                console.print(f"  - {cat}", highlight=False)
            console.print()

        # Recommendations
        if analysis.recommendations:
            console.print("[bold]Recommendations:[/bold]")
            for rec in analysis.recommendations:
                console.print(f"  [yellow]*[/yellow] {rec}", highlight=False)

    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error analyzing deck: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("deck_file", type=click.Path(exists=True))
@click.option("--budget", type=float, default=50.0, help="Budget for upgrades in USD.")
@click.option("--focus", type=str, help="Focus area for upgrades.")
def upgrade(deck_file: str, budget: float, focus: str | None) -> None:
    """Recommend upgrades for an existing deck.

    DECK_FILE is the path to a CSV/text deck list file.
    """
    try:
        from rich.console import Console

        console = Console()
        console.print(
            f"[bold]Upgrade recommendations for:[/bold] {deck_file}",
            highlight=False,
        )
        console.print(f"[dim]Budget:[/dim] ${budget:.2f}")
        if focus:
            console.print(f"[dim]Focus:[/dim] {focus}")
        console.print()

        # Upgrade recommendations require a card pool database.
        console.print(
            "[yellow]Note:[/yellow] Upgrade recommendations require a "
            "synced card database for the replacement card pool. "
            "Run 'mtg-deck sync --full' first.",
            highlight=False,
        )
    except ImportError:
        click.echo(f"Upgrade recommendations for: {deck_file}")
        click.echo(f"Budget: ${budget:.2f}")
        click.echo(
            "Note: Upgrade recommendations require a synced card database."
        )


@cli.command()
@click.argument("deck_file", type=click.Path(exists=True))
@click.option("--problem", type=str, help="Describe a problem with the deck.")
def advise(deck_file: str, problem: str | None) -> None:
    """Get AI-powered advice for a deck.

    DECK_FILE is the path to a CSV/text deck list file.
    """
    try:
        from rich.console import Console

        from mtg_deck_maker.services.advise_service import AdviseService
        from mtg_deck_maker.services.analyze_service import AnalyzeService

        console = Console()
        question = problem or "What improvements would you suggest for this deck?"

        console.print(
            f"[bold]Getting advice for:[/bold] {deck_file}", highlight=False
        )
        console.print(f"[dim]Question:[/dim] {question}")
        console.print()

        analyze_svc = AnalyzeService()
        analysis = analyze_svc.analyze_from_csv(deck_file)

        advise_svc = AdviseService()
        advice = advise_svc.get_advice(analysis, question)

        console.print("[bold]Advice:[/bold]")
        console.print(advice, highlight=False)

    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error getting advice: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("deck_file", type=click.Path(exists=True))
def validate(deck_file: str) -> None:
    """Validate a deck for Commander legality.

    DECK_FILE is the path to a CSV/text deck list file.
    """
    try:
        from rich.console import Console

        from mtg_deck_maker.io.csv_import import import_deck_from_csv

        console = Console()
        console.print(
            f"[bold]Validating:[/bold] {deck_file}", highlight=False
        )
        console.print()

        result = import_deck_from_csv(deck_file)

        if result.errors:
            console.print("[bold red]Import Errors:[/bold red]")
            for err in result.errors:
                console.print(f"  - {err}", highlight=False)
            sys.exit(1)

        total_cards = sum(c.quantity for c in result.cards)
        commanders = [c for c in result.cards if c.is_commander]

        issues: list[str] = []
        if total_cards != 100:
            issues.append(
                f"Deck has {total_cards} cards (expected 100 for Commander)."
            )
        if not commanders:
            issues.append(
                "No commander designated. Mark a card with category "
                "'Commander' or notes 'Commander'."
            )

        # Check for duplicates (Commander is singleton except basic lands)
        name_counts: dict[str, int] = {}
        for card in result.cards:
            name_counts[card.name] = (
                name_counts.get(card.name, 0) + card.quantity
            )

        basic_land_names = {"Plains", "Island", "Swamp", "Mountain", "Forest",
                           "Wastes", "Snow-Covered Plains", "Snow-Covered Island",
                           "Snow-Covered Swamp", "Snow-Covered Mountain",
                           "Snow-Covered Forest"}
        for name, count in name_counts.items():
            if count > 1 and name not in basic_land_names:
                issues.append(
                    f"Duplicate card: {name} (x{count}). "
                    "Commander decks are singleton."
                )

        if issues:
            console.print("[bold red]Validation Issues:[/bold red]")
            for issue in issues:
                console.print(f"  - {issue}", highlight=False)
        else:
            console.print(
                "[bold green]Deck is valid![/bold green] "
                f"{total_cards} cards, format: {result.format_detected}."
            )

        if result.warnings:
            console.print()
            console.print("[yellow]Warnings:[/yellow]")
            for warn in result.warnings:
                console.print(f"  - {warn}", highlight=False)

    except Exception as exc:
        click.echo(f"Error validating deck: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--full", is_flag=True, help="Full sync including bulk data.")
def sync(full: bool) -> None:
    """Sync card database with latest data sources."""
    try:
        from rich.console import Console

        from mtg_deck_maker.services.sync_service import SyncService

        console = Console()
        service = SyncService()

        result = service.sync(full=full)
        console.print(result, highlight=False)

    except Exception as exc:
        click.echo(f"Error during sync: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("--color", "-c", type=str, help="Filter by color identity.")
@click.option("--type", "card_type", type=str, help="Filter by card type.")
def search(query: str, color: str | None, card_type: str | None) -> None:
    """Search the local card database.

    QUERY is the search term for card names or oracle text.
    """
    try:
        from rich.console import Console

        console = Console()
        console.print(
            f"[bold]Searching for:[/bold] {query}", highlight=False
        )
        if color:
            console.print(f"[dim]Color filter:[/dim] {color}")
        if card_type:
            console.print(f"[dim]Type filter:[/dim] {card_type}")
        console.print()

        console.print(
            "[yellow]Note:[/yellow] Card search requires a synced local "
            "database. Run 'mtg-deck sync --full' first.",
            highlight=False,
        )
    except ImportError:
        click.echo(f"Searching for: {query}")
        click.echo("Note: Card search requires a synced local database.")


@cli.command("config")
@click.option("--show", is_flag=True, default=False, help="Display current configuration.")
def config_cmd(show: bool) -> None:
    """View or modify configuration."""
    try:
        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.config import load_config

        console = Console()

        if show:
            config = load_config()

            table = Table(title="Current Configuration")
            table.add_column("Section", style="cyan")
            table.add_column("Setting", style="green")
            table.add_column("Value")

            # General settings
            table.add_row("general", "data_dir", config.general.data_dir)
            table.add_row(
                "general",
                "cache_ttl_hours",
                str(config.general.cache_ttl_hours),
            )
            table.add_row(
                "general",
                "offline_mode",
                str(config.general.offline_mode),
            )

            # Pricing settings
            table.add_row(
                "pricing",
                "preferred_source",
                config.pricing.preferred_source,
            )
            table.add_row(
                "pricing",
                "preferred_currency",
                config.pricing.preferred_currency,
            )
            table.add_row(
                "pricing",
                "preferred_finish",
                config.pricing.preferred_finish,
            )
            table.add_row(
                "pricing",
                "price_policy",
                config.pricing.price_policy,
            )

            # Constraints settings
            table.add_row(
                "constraints",
                "max_price_per_card",
                f"${config.constraints.max_price_per_card:.2f}",
            )
            table.add_row(
                "constraints",
                "avoid_reserved_list",
                str(config.constraints.avoid_reserved_list),
            )
            table.add_row(
                "constraints",
                "allow_tutors",
                str(config.constraints.allow_tutors),
            )
            table.add_row(
                "constraints",
                "allow_fast_mana",
                str(config.constraints.allow_fast_mana),
            )

            console.print(table)

            # Show API key status
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                console.print(
                    "\n[green]ANTHROPIC_API_KEY:[/green] configured"
                )
            else:
                console.print(
                    "\n[yellow]ANTHROPIC_API_KEY:[/yellow] not set "
                    "(LLM advice will be unavailable)"
                )
        else:
            console.print(
                "Use [bold]--show[/bold] to display current configuration.",
                highlight=False,
            )
            console.print(
                "Edit [bold]~/.mtg-deck-maker.toml[/bold] to change settings.",
                highlight=False,
            )
    except ImportError:
        if show:
            click.echo("Configuration display requires the 'rich' package.")
        else:
            click.echo("Use --show to display current configuration.")
            click.echo("Edit ~/.mtg-deck-maker.toml to change settings.")

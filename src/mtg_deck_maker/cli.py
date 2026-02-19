"""Click CLI entry point for the MTG Deck Maker application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from mtg_deck_maker import __version__


def _get_db_path() -> Path:
    """Resolve the database path from config defaults."""
    from mtg_deck_maker.config import load_config

    config = load_config()
    return Path(config.general.data_dir) / "mtg_deck_maker.db"


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
        from rich.table import Table

        from mtg_deck_maker.config import AppConfig, load_config
        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.db.price_repo import PriceRepository
        from mtg_deck_maker.io.csv_export import export_deck_to_csv
        from mtg_deck_maker.models.commander import Commander
        from mtg_deck_maker.services.build_service import BuildService, BuildServiceError

        console = Console()
        config = load_config(
            config_path=Path(config_file) if config_file else None,
        )

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

        db_path = _get_db_path()
        if not db_path.exists():
            console.print(
                "[red]Error:[/red] No card database found. "
                "Run 'mtg-deck sync --full' first.",
                highlight=False,
            )
            sys.exit(1)

        with Database(db_path) as db:
            card_repo = CardRepository(db)
            price_repo = PriceRepository(db)

            # Look up commander card
            console.print("[dim]Looking up commander...[/dim]", highlight=False)
            cmd_card = card_repo.get_card_by_name(commander)
            if cmd_card is None:
                # Try fuzzy search
                results = card_repo.search_cards(commander)
                if results:
                    names = [c.name for c in results[:5]]
                    console.print(
                        f"[red]Commander '{commander}' not found.[/red]",
                        highlight=False,
                    )
                    console.print("Did you mean:", highlight=False)
                    for n in names:
                        console.print(f"  - {n}", highlight=False)
                else:
                    console.print(
                        f"[red]Commander '{commander}' not found in database.[/red]",
                        highlight=False,
                    )
                sys.exit(1)

            # Look up partner if specified
            partner_card = None
            if partner:
                partner_card = card_repo.get_card_by_name(partner)
                if partner_card is None:
                    console.print(
                        f"[red]Partner '{partner}' not found in database.[/red]",
                        highlight=False,
                    )
                    sys.exit(1)

            # Build Commander model
            cmd = Commander(
                primary=cmd_card,
                partner=partner_card,
            )

            # Get card pool within color identity
            color_identity = cmd.combined_color_identity()
            console.print(
                f"[dim]Loading card pool for {'/'.join(color_identity) or 'colorless'}...[/dim]",
                highlight=False,
            )
            card_pool = card_repo.get_cards_by_color_identity(color_identity)
            console.print(
                f"[dim]Found {len(card_pool)} candidates[/dim]",
                highlight=False,
            )

            # Get prices from DB (cheapest per card)
            console.print("[dim]Loading prices...[/dim]", highlight=False)
            prices: dict[int, float] = {}
            for card in card_pool:
                if card.id is not None:
                    price = price_repo.get_cheapest_price(card.id)
                    if price is not None:
                        prices[card.id] = price
            # Also price the commander
            if cmd_card.id is not None:
                cmd_price = price_repo.get_cheapest_price(cmd_card.id)
                if cmd_price is not None:
                    prices[cmd_card.id] = cmd_price

            # Build deck
            console.print("[dim]Building deck...[/dim]", highlight=False)
            service = BuildService(config=config)
            try:
                result = service.build(
                    commander=cmd,
                    budget=budget,
                    card_pool=card_pool,
                    prices=prices,
                    seed=seed,
                    export_csv=output is not None,
                    csv_filepath=output,
                )
            except BuildServiceError as exc:
                console.print(f"[red]Build failed:[/red] {exc}", highlight=False)
                sys.exit(1)

        console.print()
        deck = result.deck

        # Display deck summary
        console.print(
            f"[bold green]{deck.name}[/bold green]", highlight=False
        )
        console.print(
            f"Total cards: {deck.total_cards()} | "
            f"Total price: ${deck.total_price():.2f} | "
            f"Avg CMC: {deck.average_cmc():.2f}",
            highlight=False,
        )
        console.print()

        # Category breakdown table
        cat_counts: dict[str, int] = {}
        for dc in deck.cards:
            cat = dc.category or "other"
            cat_counts[cat] = cat_counts.get(cat, 0) + dc.quantity

        table = Table(title="Deck Composition")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for cat, count in sorted(
            cat_counts.items(), key=lambda x: x[1], reverse=True
        ):
            table.add_row(cat, str(count))
        console.print(table)

        # Warnings
        if result.warnings:
            console.print()
            for w in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}", highlight=False)

        # CSV output
        if output:
            console.print(f"\nDeck exported to: [bold]{output}[/bold]", highlight=False)
        else:
            # Auto-export to default path
            default_out = f"{commander.replace(' ', '_').lower()}_deck.csv"
            export_deck_to_csv(deck=deck, filepath=default_out)
            console.print(
                f"\nDeck exported to: [bold]{default_out}[/bold]",
                highlight=False,
            )

    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error building deck: {exc}", err=True)
        sys.exit(1)


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
        from rich.table import Table

        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.db.price_repo import PriceRepository
        from mtg_deck_maker.io.csv_import import import_deck_from_csv
        from mtg_deck_maker.services.upgrade_service import UpgradeService

        console = Console()

        console.print(
            f"[bold]Upgrade recommendations for:[/bold] {deck_file}",
            highlight=False,
        )
        console.print(f"[dim]Budget:[/dim] ${budget:.2f}")
        if focus:
            console.print(f"[dim]Focus:[/dim] {focus}")
        console.print()

        db_path = _get_db_path()
        if not db_path.exists():
            console.print(
                "[red]Error:[/red] No card database found. "
                "Run 'mtg-deck sync --full' first.",
                highlight=False,
            )
            sys.exit(1)

        # Import deck
        import_result = import_deck_from_csv(deck_file)
        if import_result.errors:
            for err in import_result.errors:
                console.print(f"[red]Import error:[/red] {err}", highlight=False)
            sys.exit(1)

        with Database(db_path) as db:
            card_repo = CardRepository(db)
            price_repo = PriceRepository(db)

            # Resolve imported card names to Card objects
            deck_cards = []
            name_prices: dict[str, float] = {}
            for ic in import_result.cards:
                card = card_repo.get_card_by_name(ic.name)
                if card is not None:
                    deck_cards.append(card)
                    if card.id is not None:
                        price = price_repo.get_cheapest_price(card.id)
                        if price is not None:
                            name_prices[card.name] = price

            if not deck_cards:
                console.print(
                    "[red]Could not resolve any cards from the deck file.[/red]",
                    highlight=False,
                )
                sys.exit(1)

            # Get replacement card pool
            console.print("[dim]Loading card pool...[/dim]", highlight=False)
            card_pool = card_repo.get_commander_legal_cards()

            # Get prices for pool
            for card in card_pool:
                if card.id is not None and card.name not in name_prices:
                    price = price_repo.get_cheapest_price(card.id)
                    if price is not None:
                        name_prices[card.name] = price

        # Run upgrade service
        service = UpgradeService()
        analysis, recommendations = service.recommend_from_cards(
            deck_cards=deck_cards,
            card_pool=card_pool,
            prices=name_prices,
            budget=budget,
            focus=focus,
        )

        if not recommendations:
            console.print(
                "[green]No upgrades recommended - deck looks solid![/green]",
                highlight=False,
            )
            return

        # Display recommendations
        table = Table(title=f"Top Upgrades (${budget:.2f} budget)")
        table.add_column("Out", style="red")
        table.add_column("In", style="green")
        table.add_column("Cost", justify="right", style="yellow")
        table.add_column("Reason")

        total_cost = 0.0
        for rec in recommendations:
            cost = max(rec.price_delta, 0)
            total_cost += cost
            table.add_row(
                rec.card_out,
                rec.card_in,
                f"${cost:.2f}",
                rec.reason,
            )

        console.print(table)
        console.print(
            f"\n[bold]Total upgrade cost:[/bold] ${total_cost:.2f}",
            highlight=False,
        )

    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error getting upgrades: {exc}", err=True)
        sys.exit(1)


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

        mode = "full" if full else "incremental"
        console.print(
            f"[bold]Starting {mode} sync...[/bold]", highlight=False
        )

        def progress(stage: str, current: int, total: int) -> None:
            if total > 0:
                pct = current * 100 // total
                console.print(
                    f"  [dim]{stage}:[/dim] {pct}%", highlight=False
                )
            else:
                console.print(f"  [dim]{stage}[/dim]", highlight=False)

        result = service.sync(full=full, progress_callback=progress)

        console.print()
        if result.success:
            console.print(
                "[bold green]Sync complete![/bold green]", highlight=False
            )
        else:
            console.print(
                "[bold red]Sync completed with errors.[/bold red]",
                highlight=False,
            )
        console.print(result.summary(), highlight=False)

        if result.errors:
            console.print()
            console.print("[yellow]Errors:[/yellow]")
            for err in result.errors[:10]:
                console.print(f"  - {err}", highlight=False)
            if len(result.errors) > 10:
                console.print(
                    f"  ... and {len(result.errors) - 10} more",
                    highlight=False,
                )

    except Exception as exc:
        click.echo(f"Error during sync: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("--color", "-c", type=str, help="Filter by color identity (e.g. WUB).")
@click.option("--type", "card_type", type=str, help="Filter by card type.")
@click.option("--limit", "-n", type=int, default=20, help="Max results to show.")
def search(query: str, color: str | None, card_type: str | None, limit: int) -> None:
    """Search the local card database.

    QUERY is the search term for card names.
    """
    try:
        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.db.price_repo import PriceRepository

        console = Console()

        db_path = _get_db_path()
        if not db_path.exists():
            console.print(
                "[red]Error:[/red] No card database found. "
                "Run 'mtg-deck sync --full' first.",
                highlight=False,
            )
            sys.exit(1)

        with Database(db_path) as db:
            card_repo = CardRepository(db)
            price_repo = PriceRepository(db)

            results = card_repo.search_cards(query)

            # Apply filters
            if color:
                color_set = set(color.upper())
                results = [
                    c for c in results
                    if set(c.color_identity).issubset(color_set)
                ]

            if card_type:
                results = [
                    c for c in results
                    if card_type.lower() in c.type_line.lower()
                ]

            if not results:
                console.print(
                    f"No cards found matching '{query}'.", highlight=False
                )
                return

            total = len(results)
            results = results[:limit]

            table = Table(
                title=f"Search Results ({total} total, showing {len(results)})"
            )
            table.add_column("Name", style="bold")
            table.add_column("Type", style="dim")
            table.add_column("CMC", justify="right")
            table.add_column("Colors")
            table.add_column("Price", justify="right", style="green")

            for card in results:
                price_str = "N/A"
                if card.id is not None:
                    price = price_repo.get_cheapest_price(card.id)
                    if price is not None:
                        price_str = f"${price:.2f}"

                colors = "/".join(card.color_identity) if card.color_identity else "C"
                table.add_row(
                    card.name,
                    card.type_line,
                    str(int(card.cmc)) if card.cmc == int(card.cmc) else str(card.cmc),
                    colors,
                    price_str,
                )

            console.print(table)

    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error searching: {exc}", err=True)
        sys.exit(1)


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

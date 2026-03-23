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
    if not os.environ.get("MTG_SKIP_DOTENV"):
        from dotenv import load_dotenv

        load_dotenv()


@cli.command()
@click.argument("commander")
@click.option("--budget", type=float, default=100.0, help="Target budget in USD.")
@click.option("--output", "-o", type=click.Path(), help="Output CSV path.")
@click.option("--partner", type=str, help="Partner commander name.")
@click.option("--power-level", type=int, help="Target power level (1-10).")
@click.option("--config", "config_file", type=click.Path(), help="Config file path.")
@click.option("--seed", type=int, default=42, help="Random seed for reproducibility.")
@click.option("--smart", is_flag=True, default=False, help="Use LLM research to boost card selection.")
@click.option("--provider", type=click.Choice(["auto", "openai", "anthropic"]), default="auto", help="LLM provider.")
@click.option("--model", "llm_model", type=str, default=None, help="LLM model override.")
@click.option("--no-edhrec", is_flag=True, default=False, help="Skip EDHREC data fetching.")
def build(
    commander: str,
    budget: float,
    output: str | None,
    partner: str | None,
    power_level: int | None,
    config_file: str | None,
    seed: int,
    smart: bool,
    provider: str,
    llm_model: str | None,
    no_edhrec: bool,
) -> None:
    """Generate a Commander deck for the given commander.

    COMMANDER is the name of the commander card to build around.
    """
    try:
        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.config import load_config
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.io.csv_export import export_deck_to_csv
        from mtg_deck_maker.services.build_service import (
            BuildService,
            BuildServiceError,
            CommanderNotFoundError,
        )

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
            service = BuildService(config=config)
            try:
                result = service.build_from_db(
                    commander_name=commander,
                    budget=budget,
                    db=db,
                    partner_name=partner,
                    seed=seed,
                    smart=smart,
                    provider=provider,
                    llm_model=llm_model,
                    no_edhrec=no_edhrec,
                    export_csv=output is not None,
                    csv_filepath=output,
                    progress_callback=lambda msg: console.print(
                        f"[dim]{msg}[/dim]", highlight=False
                    ),
                )
            except CommanderNotFoundError as exc:
                console.print(f"[red]{exc}[/red]", highlight=False)
                sys.exit(1)
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
            for ic in import_result.cards:
                card = card_repo.get_card_by_name(ic.name)
                if card is not None:
                    deck_cards.append(card)

            if not deck_cards:
                console.print(
                    "[red]Could not resolve any cards from the deck file.[/red]",
                    highlight=False,
                )
                sys.exit(1)

            # Get replacement card pool
            console.print("[dim]Loading card pool...[/dim]", highlight=False)
            card_pool = card_repo.get_commander_legal_cards()

            # Get prices for deck cards + pool in a single bulk query
            all_ids = [c.id for c in deck_cards if c.id is not None]
            all_ids.extend(c.id for c in card_pool if c.id is not None)
            bulk_prices = price_repo.get_cheapest_prices(all_ids)
            name_prices: dict[str, float] = {}
            for card in deck_cards + card_pool:
                if card.id is not None and card.id in bulk_prices:
                    name_prices[card.name] = bulk_prices[card.id]

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
@click.option("--provider", type=click.Choice(["auto", "openai", "anthropic"]), default="auto", help="LLM provider.")
@click.option("--model", "llm_model", type=str, default=None, help="LLM model override.")
def advise(deck_file: str, problem: str | None, provider: str, llm_model: str | None) -> None:
    """Get AI-powered advice for a deck.

    DECK_FILE is the path to a CSV/text deck list file.
    """
    try:
        from rich.console import Console

        from mtg_deck_maker.advisor.llm_provider import get_provider
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

        llm = get_provider(provider, model=llm_model)
        if llm:
            console.print(f"[dim]Using: {llm.name}[/dim]", highlight=False)

        advise_svc = AdviseService(provider=llm)
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
@click.argument("commander")
@click.option("--budget", type=float, default=None, help="Budget constraint in USD.")
@click.option("--provider", type=click.Choice(["auto", "openai", "anthropic"]), default="auto", help="LLM provider.")
@click.option("--model", "llm_model", type=str, default=None, help="LLM model override.")
@click.option("--format", "output_format", type=click.Choice(["rich", "json", "md"]), default="rich", help="Output format.")
def research(commander: str, budget: float | None, provider: str, llm_model: str | None, output_format: str) -> None:
    """Research a commander for deck-building insights.

    COMMANDER is the name of the commander card to research.
    """
    try:
        import json as json_mod

        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.advisor.llm_provider import get_provider
        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.services.research_service import ResearchService

        console = Console()

        llm = get_provider(provider, model=llm_model)
        if llm is None:
            console.print(
                "[red]Error:[/red] No LLM provider available. "
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY.",
                highlight=False,
            )
            sys.exit(1)

        # Look up commander in DB for oracle text and color identity
        db_path = _get_db_path()
        oracle_text = ""
        color_identity: list[str] = []
        if db_path.exists():
            with Database(db_path) as db:
                card_repo = CardRepository(db)
                cmd_card = card_repo.get_card_by_name(commander)
                if cmd_card:
                    oracle_text = cmd_card.oracle_text
                    color_identity = list(cmd_card.color_identity)

        colors_str = "/".join(color_identity) if color_identity else "unknown"
        console.print(
            f"[bold]Researching:[/bold] {commander} ({colors_str})",
            highlight=False,
        )
        console.print(f"[dim]Using: {llm.name}[/dim]", highlight=False)
        if budget:
            console.print(f"[dim]Budget: ${budget:.2f}[/dim]", highlight=False)
        console.print()

        research_svc = ResearchService(provider=llm)
        result = research_svc.research_commander(
            commander_name=commander,
            oracle_text=oracle_text,
            color_identity=color_identity,
            budget=budget,
        )

        if output_format == "json":
            data = {
                "commander": result.commander_name,
                "strategy_overview": result.strategy_overview,
                "key_cards": result.key_cards,
                "budget_staples": result.budget_staples,
                "combos": result.combos,
                "win_conditions": result.win_conditions,
                "cards_to_avoid": result.cards_to_avoid,
                "parse_success": result.parse_success,
            }
            click.echo(json_mod.dumps(data, indent=2))
            return

        if output_format == "md":
            lines = [f"# {result.commander_name} Research", ""]
            lines.append(f"## Strategy Overview\n{result.strategy_overview}\n")
            if result.key_cards:
                lines.append("## Key Cards")
                for c in result.key_cards:
                    lines.append(f"- {c}")
                lines.append("")
            if result.budget_staples:
                lines.append("## Budget Staples")
                for c in result.budget_staples:
                    lines.append(f"- {c}")
                lines.append("")
            if result.combos:
                lines.append("## Notable Combos")
                for c in result.combos:
                    lines.append(f"- {c}")
                lines.append("")
            if result.win_conditions:
                lines.append("## Win Conditions")
                for w in result.win_conditions:
                    lines.append(f"- {w}")
                lines.append("")
            if result.cards_to_avoid:
                lines.append("## Cards to Avoid")
                for c in result.cards_to_avoid:
                    lines.append(f"- {c}")
            click.echo("\n".join(lines))
            return

        # Rich format (default)
        if not result.parse_success:
            console.print(
                "[yellow]Warning: Could not parse structured response. "
                "Showing raw output.[/yellow]"
            )
            console.print(result.raw_response, highlight=False)
            return

        console.print("[bold]Strategy Overview[/bold]")
        console.print(f"  {result.strategy_overview}", highlight=False)
        console.print()

        if result.key_cards:
            table = Table(title=f"Key Cards ({len(result.key_cards)})")
            table.add_column("Card", style="bold")
            for card_name in result.key_cards:
                table.add_row(card_name)
            console.print(table)
            console.print()

        if result.budget_staples:
            table = Table(title=f"Budget Staples ({len(result.budget_staples)})")
            table.add_column("Card", style="green")
            for card_name in result.budget_staples:
                table.add_row(card_name)
            console.print(table)
            console.print()

        if result.combos:
            console.print("[bold]Notable Combos[/bold]")
            for combo in result.combos:
                console.print(f"  - {combo}", highlight=False)
            console.print()

        if result.win_conditions:
            console.print("[bold]Win Conditions[/bold]")
            for wc in result.win_conditions:
                console.print(f"  - {wc}", highlight=False)
            console.print()

        if result.cards_to_avoid:
            console.print("[bold red]Cards to Avoid[/bold red]")
            for card_name in result.cards_to_avoid:
                console.print(f"  - {card_name}", highlight=False)

    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error researching commander: {exc}", err=True)
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


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host address.")
@click.option("--port", type=int, default=8000, help="Bind port.")
@click.option(
    "--reload",
    "auto_reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development.",
)
def serve(host: str, port: int, auto_reload: bool) -> None:
    """Start the web API server.

    Launches the FastAPI application on the specified host and port.
    Use --reload for development (auto-restarts on code changes).
    """
    try:
        import uvicorn
    except ImportError:
        click.echo(
            "Error: uvicorn is required. Install it with: pip install uvicorn[standard]",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Starting MTG Deck Maker API on http://{host}:{port}")
    click.echo("Press Ctrl+C to stop.")

    uvicorn.run(
        "mtg_deck_maker.api.web.app:create_app",
        host=host,
        port=port,
        reload=auto_reload,
        factory=True,
    )


@cli.command()
@click.option("--host", default="127.0.0.1", help="Backend bind host.")
@click.option("--port", default=8000, type=int, help="Backend bind port.")
@click.option("--frontend-port", default=5173, type=int, help="Frontend dev server port.")
@click.option("--no-frontend", is_flag=True, default=False, help="Only start the backend API.")
def dev(host: str, port: int, frontend_port: int, no_frontend: bool) -> None:
    """Start both the API server and frontend dev server for local development."""
    import signal
    import subprocess

    from rich.console import Console

    console = Console()

    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if not frontend_dir.exists() and not no_frontend:
        console.print(
            f"[red]Error:[/red] Frontend directory not found at {frontend_dir}",
            highlight=False,
        )
        console.print(
            "Run with [bold]--no-frontend[/bold] to start only the API server.",
            highlight=False,
        )
        sys.exit(1)

    procs: list[subprocess.Popen] = []

    def cleanup(signum: int | None = None, frame: object = None) -> None:
        for p in procs:
            try:
                p.terminate()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # Start backend
        console.print(
            f"[bold green]Starting API server[/bold green] at http://{host}:{port}",
            highlight=False,
        )
        backend = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "mtg_deck_maker.api.web.app:create_app",
                "--factory",
                f"--host={host}",
                f"--port={port}",
                "--reload",
            ],
        )
        procs.append(backend)

        if not no_frontend:
            # Start frontend
            console.print(
                f"[bold green]Starting frontend[/bold green] at http://localhost:{frontend_port}",
                highlight=False,
            )
            frontend = subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", str(frontend_port)],
                cwd=str(frontend_dir),
            )
            procs.append(frontend)
            console.print()
            console.print(
                f"[bold]Open http://localhost:{frontend_port} in your browser[/bold]",
                highlight=False,
            )
        else:
            console.print()
            console.print(
                f"[bold]API available at http://{host}:{port}/api[/bold]",
                highlight=False,
            )

        console.print("[dim]Press Ctrl+C to stop[/dim]", highlight=False)

        # Wait for either process to exit
        for p in procs:
            p.wait()

    except KeyboardInterrupt:
        cleanup()
    except Exception as exc:
        cleanup()
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--save", "save_path", type=click.Path(), help="Save results to JSON file.")
@click.option("--budget", type=float, default=None, help="Override budget for all commanders.")
def benchmark(save_path: str | None, budget: float | None) -> None:
    """Run benchmark suite across reference commanders."""
    try:
        import json as json_mod
        from datetime import datetime, timezone

        from rich.console import Console
        from rich.table import Table

        from mtg_deck_maker.config import load_config
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.metrics.benchmark import (
            BenchmarkResult,
            get_benchmark_commanders,
            validate_benchmark_result,
        )
        from mtg_deck_maker.metrics.comparison import compute_metrics
        from mtg_deck_maker.services.build_service import (
            BuildService,
            BuildServiceError,
        )

        console = Console()
        config = load_config()

        db_path = _get_db_path()
        if not db_path.exists():
            console.print(
                "[red]Error:[/red] No card database found. "
                "Run 'mtg-deck sync --full' first.",
                highlight=False,
            )
            sys.exit(1)

        commanders = get_benchmark_commanders()
        console.print(
            f"[bold]Running benchmark suite[/bold] ({len(commanders)} commanders)",
            highlight=False,
        )
        console.print()

        table = Table(title="Benchmark Results")
        table.add_column("Commander", style="bold")
        table.add_column("Archetype", style="cyan")
        table.add_column("Cards", justify="right")
        table.add_column("Price", justify="right", style="green")
        table.add_column("Cat Coverage", justify="right")
        table.add_column("Curve Smooth", justify="right")
        table.add_column("EDHREC Overlap", justify="right")
        table.add_column("Warnings")

        pass_count = 0
        fail_count = 0
        json_commanders: dict[str, dict] = {}

        with Database(db_path) as db:
            service = BuildService(config=config)

            for cmd in commanders:
                cmd_budget = budget if budget is not None else cmd.budget
                try:
                    result = service.build_from_db(
                        commander_name=cmd.name,
                        budget=cmd_budget,
                        db=db,
                        seed=42,
                        no_edhrec=True,
                    )
                except BuildServiceError as exc:
                    console.print(
                        f"[yellow]Warning:[/yellow] {cmd.name} failed to build: {exc}",
                        highlight=False,
                    )
                    fail_count += 1
                    table.add_row(
                        cmd.name,
                        cmd.archetype,
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        f"[red]Build failed: {exc}[/red]",
                    )
                    json_commanders[cmd.name] = {
                        "archetype": cmd.archetype,
                        "card_count": 0,
                        "total_price": 0.0,
                        "category_coverage": 0.0,
                        "curve_smoothness": 0.0,
                        "edhrec_overlap": 0.0,
                        "warnings": [f"Build failed: {exc}"],
                    }
                    continue

                deck = result.deck
                metrics = compute_metrics(deck)

                bench_result = BenchmarkResult(
                    commander_name=cmd.name,
                    metrics=metrics,
                    deck_card_count=deck.total_cards(),
                )
                warnings = validate_benchmark_result(bench_result, cmd)

                # Extract metric values
                cc_val = (
                    metrics.category_coverage.overall_pct
                    if metrics.category_coverage is not None
                    else None
                )
                cs_val = (
                    metrics.curve_smoothness.smoothness
                    if metrics.curve_smoothness is not None
                    else None
                )
                eo_val = (
                    metrics.edhrec_overlap.overlap_pct
                    if metrics.edhrec_overlap is not None
                    else None
                )

                cc_str = f"{cc_val * 100:.1f}%" if cc_val is not None else "N/A"
                cs_str = f"{cs_val:.2f}" if cs_val is not None else "N/A"
                eo_str = f"{eo_val * 100:.1f}%" if eo_val is not None else "N/A"

                if warnings:
                    fail_count += 1
                    warn_str = f"[red]{len(warnings)} issue(s)[/red]"
                else:
                    pass_count += 1
                    warn_str = "[green]PASS[/green]"

                table.add_row(
                    cmd.name,
                    cmd.archetype,
                    str(deck.total_cards()),
                    f"${metrics.total_price:.2f}",
                    cc_str,
                    cs_str,
                    eo_str,
                    warn_str,
                )

                json_commanders[cmd.name] = {
                    "archetype": cmd.archetype,
                    "card_count": deck.total_cards(),
                    "total_price": metrics.total_price,
                    "category_coverage": cc_val if cc_val is not None else 0.0,
                    "curve_smoothness": cs_val if cs_val is not None else 0.0,
                    "edhrec_overlap": eo_val if eo_val is not None else 0.0,
                    "warnings": warnings,
                }

                # Print per-commander warnings
                for w in warnings:
                    console.print(
                        f"  [yellow]Warning:[/yellow] {w}", highlight=False
                    )

        console.print(table)
        console.print()
        console.print(
            f"[bold]Summary:[/bold] {pass_count} passed, {fail_count} failed "
            f"out of {len(commanders)} commanders.",
            highlight=False,
        )

        if save_path:
            json_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "commanders": json_commanders,
            }
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w") as f:
                json_mod.dump(json_data, f, indent=2)
            console.print(
                f"\nResults saved to [bold]{save_path}[/bold]",
                highlight=False,
            )

    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error running benchmark: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--commanders", "-n", type=int, default=50, help="Number of commanders to train on.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Model output path.")
@click.option("--test-split", type=float, default=0.2, help="Fraction of data for testing.")
def train(commanders: int, output: str | None, test_split: float) -> None:
    """Train the ML power prediction model from EDHREC data."""
    try:
        from rich.console import Console

        console = Console()

        np = __import__("numpy")
        sklearn = __import__("sklearn")  # noqa: F841

        from mtg_deck_maker.db.card_repo import CardRepository
        from mtg_deck_maker.db.database import Database
        from mtg_deck_maker.db.edhrec_repo import EdhrecRepository
        from mtg_deck_maker.ml.trainer import (
            DEFAULT_MODEL_PATH,
            build_dataset,
            evaluate_model,
            save_model,
            train_model,
        )

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
            edhrec_repo = EdhrecRepository(db)
            edhrec_repo.create_tables()

            # Collect commanders with EDHREC data
            console.print(
                f"[bold]Training power prediction model[/bold] "
                f"(up to {commanders} commanders)",
                highlight=False,
            )

            commander_cards: list[tuple] = []

            # Get distinct commander names from EDHREC data
            cursor = db.execute(
                "SELECT DISTINCT commander_name FROM edhrec_commander_cards"
            )
            cmd_names = [row[0] for row in cursor.fetchall()]

            for cmd_name in cmd_names:
                if len(commander_cards) >= commanders:
                    break

                cmd_card = card_repo.get_card_by_name(cmd_name)
                if cmd_card is None:
                    continue

                top_cards = edhrec_repo.get_top_cards(cmd_name, limit=500)
                if len(top_cards) < 10:
                    continue

                # Attach Card objects to EDHREC entries
                for entry in top_cards:
                    resolved = card_repo.get_card_by_name(entry.card_name)
                    if resolved is not None:
                        entry._card = resolved  # type: ignore[attr-defined]

                commander_cards.append((cmd_card, top_cards))  # type: ignore[arg-type]

            if not commander_cards:
                console.print(
                    "[red]Error:[/red] No commanders with EDHREC data found. "
                    "Run 'mtg-deck build --smart <commander>' first to cache data.",
                    highlight=False,
                )
                sys.exit(1)

            console.print(
                f"[dim]Found {len(commander_cards)} commanders with EDHREC data[/dim]",
                highlight=False,
            )

            # Build card pool function for negative sampling
            def card_pool_fn(commander: object) -> list:
                from mtg_deck_maker.models.card import Card as CardModel
                if isinstance(commander, CardModel):
                    ci = list(commander.color_identity)
                    return card_repo.get_cards_by_color_identity(ci)
                return []

            # Build dataset
            console.print("[dim]Building dataset...[/dim]", highlight=False)
            x, y = build_dataset(commander_cards, card_pool_fn=card_pool_fn)

            if x.size == 0:
                console.print(
                    "[red]Error:[/red] No training samples generated.",
                    highlight=False,
                )
                sys.exit(1)

            console.print(
                f"[dim]Dataset: {x.shape[0]} samples, {x.shape[1]} features[/dim]",
                highlight=False,
            )

            # Train/test split
            split_idx = int(len(x) * (1 - test_split))
            indices = np.random.RandomState(42).permutation(len(x))
            train_idx, test_idx = indices[:split_idx], indices[split_idx:]
            x_train, x_test = x[train_idx], x[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            console.print(
                f"[dim]Training on {len(x_train)} samples, "
                f"testing on {len(x_test)} samples[/dim]",
                highlight=False,
            )

            # Train
            console.print("[dim]Training model...[/dim]", highlight=False)
            model = train_model(x_train, y_train)

            # Evaluate
            metrics = evaluate_model(model, x_test, y_test)
            console.print()
            console.print("[bold]Model Performance:[/bold]")
            console.print(f"  MAE:  {metrics['mae']:.4f}")
            console.print(f"  RMSE: {metrics['rmse']:.4f}")
            console.print(f"  R²:   {metrics['r2']:.4f}")

            # Save
            save_path = save_model(model, output or DEFAULT_MODEL_PATH)
            console.print()
            console.print(
                f"[bold green]Model saved to {save_path}[/bold green]",
                highlight=False,
            )

    except ImportError as exc:
        click.echo(
            f"Error: ML dependencies not installed. "
            f"Install with: pip install mtg-deck-maker[ml] ({exc})",
            err=True,
        )
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Error training model: {exc}", err=True)
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

            # LLM settings table
            llm_table = Table(title="LLM Settings")
            llm_table.add_column("Setting", style="cyan")
            llm_table.add_column("Value")
            llm_table.add_row("provider", config.llm.provider)
            llm_table.add_row("openai_model", config.llm.openai_model)
            llm_table.add_row("anthropic_model", config.llm.anthropic_model)
            llm_table.add_row("max_tokens", str(config.llm.max_tokens))
            llm_table.add_row("temperature", str(config.llm.temperature))
            llm_table.add_row("timeout_s", str(config.llm.timeout_s))
            llm_table.add_row("max_retries", str(config.llm.max_retries))
            llm_table.add_row("priority_bonus", str(config.llm.priority_bonus))
            llm_table.add_row(
                "research_enabled", str(config.llm.research_enabled)
            )
            console.print()
            console.print(llm_table)

            # Show API key status for both providers
            console.print()
            openai_key = os.environ.get("OPENAI_API_KEY")
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            if openai_key:
                console.print(
                    "[green]OPENAI_API_KEY:[/green] configured"
                )
            else:
                console.print(
                    "[yellow]OPENAI_API_KEY:[/yellow] not set"
                )
            if anthropic_key:
                console.print(
                    "[green]ANTHROPIC_API_KEY:[/green] configured"
                )
            else:
                console.print(
                    "[yellow]ANTHROPIC_API_KEY:[/yellow] not set"
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

import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box

load_dotenv()
console = Console()


def _require_env():
    missing = [k for k in ("ANTHROPIC_API_KEY", "T212_API_KEY") if not os.environ.get(k)]
    if missing:
        console.print(f"[red]Missing env vars: {', '.join(missing)}[/red]")
        console.print("Copy [bold].env.example[/bold] to [bold].env[/bold] and fill in your keys.")
        sys.exit(1)


@click.group()
def cli():
    """Phase Storm — your AI portfolio assistant."""
    pass


@cli.command()
def sync():
    """Sync portfolio data from Trading212."""
    _require_env()
    from .clients.trading212 import Trading212Client
    from .db.database import get_session

    console.print("[cyan]Syncing from Trading212...[/cyan]")
    client = Trading212Client()
    db = get_session()
    try:
        stats = client.sync(db)
        console.print(
            f"[green]Done![/green] "
            f"Pies: {stats['pies']}  Positions: {stats['positions']}  "
            f"New companies: {stats['companies']}"
        )
    except Exception as e:
        console.print(f"[red]Sync failed:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
def portfolio():
    """Show current portfolio positions."""
    _require_env()
    from .agent.tools import get_portfolio_summary

    data = get_portfolio_summary()
    if "error" in data:
        console.print(f"[red]{data['error']}[/red]")
        return

    console.print(Panel(
        f"[bold]Total value:[/bold] {data['total_value']:,.2f}   "
        f"[bold]P&L:[/bold] [{'green' if data['total_ppl'] >= 0 else 'red'}]"
        f"{data['total_ppl']:+,.2f}[/]",
        title="[bold cyan]Phase Storm Portfolio[/bold cyan]",
        border_style="cyan",
    ))

    def _position_table(positions: list, title: str):
        if not positions:
            return
        t = Table(title=title, box=box.SIMPLE_HEAVY, show_header=True)
        t.add_column("Ticker", style="bold")
        t.add_column("Name")
        t.add_column("Qty", justify="right")
        t.add_column("Avg Price", justify="right")
        t.add_column("Current", justify="right")
        t.add_column("Value", justify="right")
        t.add_column("P&L", justify="right")
        t.add_column("P&L %", justify="right")
        for p in positions:
            ppl_color = "green" if p["ppl"] >= 0 else "red"
            t.add_row(
                p["ticker"],
                p["name"],
                str(p["quantity"]),
                f"{p['avg_price']:.4f}",
                f"{p['current_price']:.4f}",
                f"{p['total_value']:,.2f}",
                f"[{ppl_color}]{p['ppl']:+,.2f}[/]",
                f"[{ppl_color}]{p['ppl_pct']:+.2f}%[/]",
            )
        console.print(t)

    for pie_name, positions in data["positions_by_pie"].items():
        _position_table(positions, pie_name)

    if data["standalone_positions"]:
        _position_table(data["standalone_positions"], "Standalone")


@cli.command()
def chat():
    """Start an interactive chat session with your portfolio AI."""
    _require_env()
    from .agent.agent import PhaseStormAgent

    agent = PhaseStormAgent()
    console.print(Panel(
        "Chat with [bold cyan]Phase Storm[/bold cyan] about your portfolio.\n"
        "Type [bold]exit[/bold] or [bold]quit[/bold] to leave. "
        "Type [bold]reset[/bold] to start a new conversation.",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        stripped = user_input.strip().lower()
        if stripped in ("exit", "quit"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if stripped == "reset":
            agent.reset()
            console.print("[dim]Conversation reset.[/dim]")
            continue
        if not stripped:
            continue

        with console.status("[cyan]Thinking...[/cyan]"):
            try:
                reply = agent.chat(user_input)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                continue

        console.print(Panel(Markdown(reply), title="[bold cyan]Phase Storm[/bold cyan]", border_style="cyan"))


def main():
    cli()

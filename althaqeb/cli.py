"""Althaqeb CLI — entry point for all terminal operations."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from althaqeb import __version__
from althaqeb.core.engine import Engine
from althaqeb.core.target import TargetProfiler
from althaqeb.core.session import SessionManager
from althaqeb.utils.logger import get_logger

app = typer.Typer(
    name="althaqeb",
    help="الثاقب — AI Security Lifecycle Framework",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()
logger = get_logger(__name__)

BANNER = """
[bold cyan]  ████████╗██╗  ██╗ █████╗  ██████╗ ██╗   ██╗███████╗██████╗ [/bold cyan]
[bold cyan]     ██╔══╝██║  ██║██╔══██╗██╔═══██╗██║   ██║██╔════╝██╔══██╗[/bold cyan]
[bold cyan]     ██║   ███████║███████║██║   ██║██║   ██║█████╗  ██████╔╝ [/bold cyan]
[bold cyan]     ██║   ██╔══██║██╔══██║██║▄▄ ██║██║   ██║██╔══╝  ██╔══██╗ [/bold cyan]
[bold cyan]     ██║   ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████╗██████╔╝ [/bold cyan]
[bold cyan]     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚══▀▀═╝  ╚═════╝ ╚══════╝╚═════╝  [/bold cyan]
[bold white]  الثاقب — AI Security Lifecycle Framework[/bold white]
[dim]  github.com/0xMsecurity/althaqeb                        v{version}[/dim]
"""


def print_banner() -> None:
    console.print(BANNER.format(version=__version__))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """الثاقب — AI Security Lifecycle Framework.

    The piercing eye of AI security. Built in Bahrain for the GCC and beyond.
    """
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print(ctx.get_help())


@app.command()
def version() -> None:
    """Show version and build information."""
    print_banner()
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_row("[dim]Version[/dim]", f"[bold cyan]{__version__}[/bold cyan]")
    table.add_row("[dim]Python[/dim]", f"[cyan]{sys.version.split()[0]}[/cyan]")
    table.add_row("[dim]Framework[/dim]", "[cyan]الثاقب — Althaqeb[/cyan]")
    table.add_row("[dim]Origin[/dim]", "[cyan]Bahrain 🇧🇭[/cyan]")
    table.add_row("[dim]License[/dim]", "[cyan]MIT[/cyan]")
    console.print(table)


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8765, help="Port to bind"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't auto-open browser"),
) -> None:
    """Launch the الثاقب GUI dashboard in your browser."""
    print_banner()

    try:
        import uvicorn
        from althaqeb.api.server import create_app
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        console.print("Run: [cyan]pip install althaqeb[ui][/cyan]")
        raise typer.Exit(1)

    url = f"http://{host}:{port}"
    console.print(
        Panel(
            f"[bold cyan]الثاقب GUI[/bold cyan] running at [bold white]{url}[/bold white]\n"
            f"[dim]Press Ctrl+C to stop[/dim]",
            border_style="cyan",
            title="[bold]Dashboard Starting[/bold]",
        )
    )

    if not no_browser:
        import threading
        import time
        def _open():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    api_app = create_app()
    uvicorn.run(api_app, host=host, port=port, log_level="warning")


@app.command()
def scan(
    target: str = typer.Option(..., "--target", "-t", help="Target URL or API endpoint"),
    module: str = typer.Option("all", "--module", "-m", help="Module: all|injection|extraction|jailbreak"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save results to file"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key for target"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run a full security scan against a target AI system."""
    print_banner()

    console.print(Panel(
        f"[bold]Target:[/bold] [cyan]{target}[/cyan]\n"
        f"[bold]Module:[/bold] [yellow]{module}[/yellow]",
        title="[bold cyan]Starting Scan[/bold cyan]",
        border_style="cyan",
    ))

    engine = Engine(verbose=verbose)

    with console.status("[bold cyan]Profiling target...[/bold cyan]"):
        profile = engine.profile_target(target, api_key=api_key)

    _print_profile(profile)

    console.print(f"\n[bold cyan]Running module:[/bold cyan] [yellow]{module}[/yellow]\n")

    session = engine.run_scan(target, module=module, api_key=api_key, profile=profile)

    _print_findings(session)

    if output:
        results = session.to_dict()
        output.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        console.print(f"\n[green]Results saved to:[/green] [cyan]{output}[/cyan]")

    _print_summary(session)


@app.command()
def attack(
    target: str = typer.Option(..., "--target", "-t", help="Target URL or API endpoint"),
    type_: str = typer.Option("injection", "--type", help="Attack: injection|extraction|jailbreak|agent"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save results"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a specific attack module against a target."""
    print_banner()

    console.print(Panel(
        f"[bold]Target:[/bold] [cyan]{target}[/cyan]\n"
        f"[bold]Attack:[/bold] [red]{type_}[/red]",
        title="[bold red]Attack Module[/bold red]",
        border_style="red",
    ))

    engine = Engine(verbose=verbose)
    session = engine.run_attack(target, attack_type=type_, api_key=api_key)

    _print_findings(session)
    _print_summary(session)

    if output:
        output.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
        console.print(f"\n[green]Results saved to:[/green] [cyan]{output}[/cyan]")


@app.command()
def profile(
    target: str = typer.Option(..., "--target", "-t", help="Target URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k"),
) -> None:
    """Profile and fingerprint a target AI system."""
    print_banner()

    engine = Engine()
    with console.status("[bold cyan]Profiling target...[/bold cyan]"):
        result = engine.profile_target(target, api_key=api_key)

    _print_profile(result)


@app.command()
def report(
    session_id: str = typer.Option(..., "--session", "-s", help="Session ID"),
    format_: str = typer.Option("html", "--format", "-f", help="Format: html|json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Generate a report for a completed scan session."""
    print_banner()

    sm = SessionManager()
    session = sm.load(session_id)

    if session is None:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)

    from althaqeb.reports.generator import ReportGenerator
    gen = ReportGenerator()

    if format_ == "html":
        content = gen.generate_html(session)
        suffix = ".html"
    else:
        content = json.dumps(session.to_dict(), indent=2, ensure_ascii=False)
        suffix = ".json"

    if output is None:
        output = Path(f"althaqeb_report_{session_id[:8]}{suffix}")

    output.write_text(content, encoding="utf-8")
    console.print(f"[green]Report saved:[/green] [cyan]{output}[/cyan]")


@app.command("modules")
def list_modules() -> None:
    """List all available attack modules and their status."""
    print_banner()

    table = Table(
        title="[bold cyan]Available Modules[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("Layer", style="bold white", width=12)
    table.add_column("Module", style="cyan", width=20)
    table.add_column("Techniques", justify="center", width=12)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Description", style="dim")

    modules = [
        ("ATTACK", "injection",   "30+", "[green]✓ Active[/green]",   "Prompt injection — all vectors"),
        ("ATTACK", "extraction",  "20+", "[green]✓ Active[/green]",   "System prompt extraction"),
        ("ATTACK", "jailbreak",   "15+", "[green]✓ Active[/green]",   "Guardrail bypass techniques"),
        ("ATTACK", "agent",       "10+", "[yellow]◐ Partial[/yellow]", "Agent tool abuse simulation"),
        ("TRUST",  "model-audit", "8",   "[yellow]◐ Partial[/yellow]", "Pre-deployment model audit"),
        ("TRUST",  "supply-chain","6",   "[dim]○ Planned[/dim]",      "Supply chain integrity"),
        ("DEFEND", "rag-monitor", "5",   "[dim]○ Planned[/dim]",      "RAG integrity monitoring"),
        ("DEFEND", "anomaly",     "7",   "[dim]○ Planned[/dim]",      "Behavioral anomaly detection"),
        ("IDENTITY","deepfake",   "4",   "[dim]○ Planned[/dim]",      "Deepfake & proof-of-human"),
        ("INTEL",  "ttp-db",      "84+", "[yellow]◐ Partial[/yellow]", "MITRE ATLAS TTP taxonomy"),
    ]

    for layer, mod, tech, status, desc in modules:
        layer_color = {
            "ATTACK": "[red]ATTACK[/red]",
            "TRUST":  "[yellow]TRUST[/yellow]",
            "DEFEND": "[green]DEFEND[/green]",
            "IDENTITY": "[blue]IDENTITY[/blue]",
            "INTEL":  "[magenta]INTEL[/magenta]",
        }.get(layer, layer)
        table.add_row(layer_color, mod, tech, status, desc)

    console.print(table)
    console.print("\n[dim]Use [cyan]althaqeb attack --type <module>[/cyan] to run a specific module[/dim]")


def _print_profile(profile: dict) -> None:
    table = Table(
        title="[bold cyan]Target Profile[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=False,
    )
    table.add_column("Property", style="bold white", width=24)
    table.add_column("Value", style="cyan")

    for key, val in profile.items():
        if isinstance(val, bool):
            display = "[green]✓ Yes[/green]" if val else "[red]✗ No[/red]"
        elif val is None:
            display = "[dim]Unknown[/dim]"
        else:
            display = str(val)
        table.add_row(key.replace("_", " ").title(), display)

    console.print(table)


def _print_findings(session) -> None:
    findings = session.findings if hasattr(session, "findings") else []

    if not findings:
        console.print("\n[green]No vulnerabilities found in this scan.[/green]")
        return

    table = Table(
        title=f"[bold red]Findings ({len(findings)})[/bold red]",
        box=box.ROUNDED,
        border_style="red",
        show_lines=True,
    )
    table.add_column("ID", style="dim", width=8)
    table.add_column("Technique", style="bold white", width=28)
    table.add_column("Severity", justify="center", width=12)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Confidence", justify="center", width=12)

    severity_colors = {
        "CRITICAL": "[bold red]CRITICAL[/bold red]",
        "HIGH":     "[red]HIGH[/red]",
        "MEDIUM":   "[yellow]MEDIUM[/yellow]",
        "LOW":      "[green]LOW[/green]",
        "INFO":     "[dim]INFO[/dim]",
    }

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "INFO")
        score = f.get("aivss_score", 0.0)
        conf = f.get("confidence", 0.0)
        table.add_row(
            f"F-{i:03d}",
            f.get("technique", "Unknown"),
            severity_colors.get(sev, sev),
            f"[bold]{score:.1f}[/bold]",
            f"{conf:.0%}",
        )

    console.print(table)


def _print_summary(session) -> None:
    findings = session.findings if hasattr(session, "findings") else []

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev = f.get("severity", "INFO")
        counts[sev] = counts.get(sev, 0) + 1

    total_score = max((f.get("aivss_score", 0.0) for f in findings), default=0.0)

    if total_score >= 9.0:
        risk_label = "[bold red]CRITICAL RISK[/bold red]"
    elif total_score >= 7.0:
        risk_label = "[red]HIGH RISK[/red]"
    elif total_score >= 4.0:
        risk_label = "[yellow]MEDIUM RISK[/yellow]"
    elif total_score > 0:
        risk_label = "[green]LOW RISK[/green]"
    else:
        risk_label = "[green]CLEAN[/green]"

    summary_text = (
        f"Overall Risk: {risk_label}  |  Score: [bold]{total_score:.1f}[/bold]/10.0\n"
        f"[red]Critical: {counts['CRITICAL']}[/red]  "
        f"[red]High: {counts['HIGH']}[/red]  "
        f"[yellow]Medium: {counts['MEDIUM']}[/yellow]  "
        f"[green]Low: {counts['LOW']}[/green]\n\n"
        f"[dim]Run [cyan]althaqeb report --session {getattr(session, 'id', 'SESSION_ID')}[/cyan] to generate full report[/dim]"
    )

    console.print(Panel(
        summary_text,
        title="[bold cyan]Scan Summary — الثاقب[/bold cyan]",
        border_style="cyan",
    ))


if __name__ == "__main__":
    app()

import shutil
import subprocess
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .templates import SCHEMA_TEMPLATE, EMPTY_INDEX, EMPTY_LOG
from .config import find_wiki_root, save_config, load_config
from .agent import run_agent, build_ingest_prompt, build_query_prompt, build_lint_prompt

app = typer.Typer(
    name="wiki",
    help="Build personal knowledge bases with LLMs.",
    no_args_is_help=True,
)
console = Console()


def _is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def _pdf_text_output_path(source: Path) -> Path:
    if source.suffix.lower() == ".txt":
        return source.with_name(f"{source.stem}-converted.txt")
    return source.with_suffix(".txt")


def _convert_pdf_to_text(source: Path, *, delete_source: bool = False) -> Path:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        console.print(
            "[red]PDF source detected, but `pdftotext` is not installed.[/red]\n"
            "Install Poppler tools, or convert the PDF to text/markdown before ingesting."
        )
        raise typer.Exit(1)

    output = _pdf_text_output_path(source)
    console.print(f"[yellow]PDF detected. Converting to text:[/yellow] {output.name}")
    try:
        subprocess.run(
            [pdftotext, str(source), str(output)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        error = e.stderr.strip() or e.stdout.strip() or "Unknown conversion error"
        console.print(f"[red]Failed to convert PDF to text:[/red] {error}")
        raise typer.Exit(1)

    if not output.exists() or not output.read_text(encoding="utf-8", errors="replace").strip():
        console.print("[red]PDF conversion produced no extractable text.[/red]")
        raise typer.Exit(1)

    if delete_source:
        source.unlink()
        console.print(f"[yellow]Deleted original PDF:[/yellow] {source.name}")

    return output


def _get_wiki_root(wiki: Optional[Path]) -> Path:
    if wiki:
        root = wiki.resolve()
        if not (root / "schema.md").exists():
            console.print(f"[red]No wiki found at {root}. Run `wiki init` first.[/red]")
            raise typer.Exit(1)
        return root

    root = find_wiki_root(Path.cwd())
    if root is None:
        console.print(
            "[red]No wiki found in current directory or parents. "
            "Run `wiki init` to create one.[/red]"
        )
        raise typer.Exit(1)
    return root


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Directory to initialize wiki in"),
    name: str = typer.Option("My Wiki", "--name", "-n", help="Wiki name"),
):
    """Initialize a new wiki project."""
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)

    if (root / "schema.md").exists():
        console.print(f"[yellow]Wiki already exists at {root}[/yellow]")
        raise typer.Exit(1)

    # Create directory structure
    (root / "raw" / "assets").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)

    # Write schema
    (root / "schema.md").write_text(SCHEMA_TEMPLATE)

    # Write empty index and log
    index_content = EMPTY_INDEX.replace("Wiki Index", f"{name} — Index")
    (root / "wiki" / "index.md").write_text(index_content)
    (root / "wiki" / "log.md").write_text(EMPTY_LOG.replace("Wiki Log", f"{name} — Log"))

    # Write .gitignore
    (root / ".gitignore").write_text("raw/assets/\n")

    console.print(Panel(
        f"[bold green]Wiki initialized![/bold green]\n\n"
        f"📁 [cyan]{root}[/cyan]\n\n"
        f"Next steps:\n"
        f"  1. Drop source files into [cyan]raw/[/cyan]\n"
        f"  2. Run [bold]wiki ingest raw/your-file.md[/bold]\n"
        f"  3. Run [bold]wiki query \"your question\"[/bold]",
        title=f"[bold]{name}[/bold]",
        border_style="green",
    ))


@app.command()
def ingest(
    source: Path = typer.Argument(..., help="Source file to ingest"),
    wiki: Optional[Path] = typer.Option(None, "--wiki", "-w", help="Wiki root directory"),
    thinking: bool = typer.Option(False, "--thinking", help="Show LLM thinking (Anthropic only)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: anthropic, openai"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model override"),
    delete_pdf: bool = typer.Option(
        False,
        "--delete-pdf",
        help="Delete a PDF source after converting it to text",
    ),
):
    """Ingest a source document into the wiki."""
    root = _get_wiki_root(wiki)

    if not source.exists():
        console.print(f"[red]Source file not found: {source}[/red]")
        raise typer.Exit(1)

    ingest_source = (
        _convert_pdf_to_text(source, delete_source=delete_pdf)
        if _is_pdf(source)
        else source
    )

    console.print(f"[bold]Ingesting:[/bold] {ingest_source.name}")
    console.print(f"[dim]Wiki root: {root}[/dim]\n")

    system, user = build_ingest_prompt(root, ingest_source.resolve())
    result = run_agent(root, system, user, show_thinking=thinking, provider=provider, model=model)

    if result:
        console.print("\n")
        console.print(Markdown(result))


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask the wiki"),
    wiki: Optional[Path] = typer.Option(None, "--wiki", "-w", help="Wiki root directory"),
    save: bool = typer.Option(False, "--save", "-s", help="Save answer as wiki page"),
    format: str = typer.Option(
        "markdown",
        "--format", "-f",
        help="Output format: markdown, table, marp",
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save answer to file"),
    thinking: bool = typer.Option(False, "--thinking", help="Show LLM thinking (Anthropic only)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: anthropic, openai"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model override"),
):
    """Query the wiki with a question."""
    root = _get_wiki_root(wiki)

    console.print(f"[bold]Query:[/bold] {question}")
    console.print(f"[dim]Format: {format} | Wiki root: {root}[/dim]\n")

    # Inject save instruction into query if requested
    full_question = question
    if save:
        full_question += (
            "\n\nIMPORTANT: After synthesizing the answer, save it as a permanent "
            "wiki page in wiki/concepts/ (choose an appropriate filename)."
        )

    system, user = build_query_prompt(root, full_question, format)
    result = run_agent(root, system, user, show_thinking=thinking, provider=provider, model=model)

    if result:
        console.print("\n")
        if output:
            output.write_text(result)
            console.print(f"[green]Saved to {output}[/green]")
        else:
            console.print(Markdown(result))


@app.command()
def lint(
    wiki: Optional[Path] = typer.Option(None, "--wiki", "-w", help="Wiki root directory"),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix issues found"),
    thinking: bool = typer.Option(False, "--thinking", help="Show LLM thinking (Anthropic only)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: anthropic, openai"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model override"),
):
    """Run health checks on the wiki."""
    root = _get_wiki_root(wiki)

    console.print(f"[bold]Linting wiki:[/bold] {root}")
    console.print()

    system, user = build_lint_prompt(root)
    if fix:
        user += "\n\nPlease also fix the issues you find directly."

    result = run_agent(root, system, user, show_thinking=thinking, provider=provider, model=model)

    if result:
        console.print("\n")
        console.print(Markdown(result))


@app.command()
def status(
    wiki: Optional[Path] = typer.Option(None, "--wiki", "-w", help="Wiki root directory"),
):
    """Show wiki statistics."""
    root = _get_wiki_root(wiki)

    wiki_dir = root / "wiki"
    raw_dir = root / "raw"

    sources = list((wiki_dir / "sources").glob("*.md")) if (wiki_dir / "sources").exists() else []
    concepts = list((wiki_dir / "concepts").glob("*.md")) if (wiki_dir / "concepts").exists() else []
    entities = list((wiki_dir / "entities").glob("*.md")) if (wiki_dir / "entities").exists() else []
    raw_files = list(raw_dir.glob("*")) if raw_dir.exists() else []
    raw_files = [f for f in raw_files if f.is_file() and f.suffix != ""]

    # Count words in wiki
    total_words = 0
    for md in (wiki_dir).rglob("*.md"):
        try:
            total_words += len(md.read_text().split())
        except Exception:
            pass

    console.print(Panel(
        f"[bold]Wiki:[/bold] {root}\n\n"
        f"  📄 Sources:  [cyan]{len(sources)}[/cyan] pages\n"
        f"  💡 Concepts: [cyan]{len(concepts)}[/cyan] pages\n"
        f"  👤 Entities: [cyan]{len(entities)}[/cyan] pages\n"
        f"  📁 Raw files: [cyan]{len(raw_files)}[/cyan]\n"
        f"  📝 Total wiki words: [cyan]{total_words:,}[/cyan]",
        title="[bold]Wiki Status[/bold]",
        border_style="blue",
    ))


@app.command()
def config(
    provider: Optional[str] = typer.Option(None, "--provider", help="Default provider: anthropic, openai"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for the selected provider"),
    model: Optional[str] = typer.Option(None, "--model", help="Default model override"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
):
    """Configure wiki-builder settings (provider, API key, default model)."""
    cfg = load_config()
    changed = False

    if provider:
        if provider not in ("anthropic", "openai"):
            console.print(f"[red]Unknown provider: {provider!r}. Use 'anthropic' or 'openai'.[/red]")
            raise typer.Exit(1)
        cfg["provider"] = provider
        changed = True
        console.print(f"[green]Provider set to: {provider}[/green]")

    if api_key:
        # Store under provider-specific key if provider is known
        p = provider or cfg.get("provider", "anthropic")
        cfg[f"{p}_api_key"] = api_key
        changed = True
        console.print(f"[green]API key saved for: {p}[/green]")

    if model:
        cfg["model"] = model
        changed = True
        console.print(f"[green]Default model set to: {model}[/green]")

    if changed:
        save_config(cfg)

    if show or not changed:
        p = cfg.get("provider", "anthropic")
        m = cfg.get("model", "(default)")
        console.print(f"provider: [cyan]{p}[/cyan]")
        console.print(f"model:    [cyan]{m}[/cyan]")
        for key_name in ("anthropic_api_key", "openai_api_key", "api_key"):
            if cfg.get(key_name):
                v = cfg[key_name]
                masked = v[:8] + "..." + v[-4:]
                console.print(f"{key_name}: {masked}")
        console.print("\n[dim]Env vars: ANTHROPIC_API_KEY, OPENAI_API_KEY, WIKI_PROVIDER[/dim]")

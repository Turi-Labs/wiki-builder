"""
Agentic loop: LLM + file tools = wiki maintainer.
Supports Anthropic (Claude) and OpenAI (GPT-4o etc.) as providers.
"""

import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.live import Live

from .tools import WikiTools
from .config import get_provider_config

console = Console()

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-6",
    "openai": "gpt-4o",
}


# ---------------------------------------------------------------------------
# Anthropic backend
# ---------------------------------------------------------------------------

def _run_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list,
    tools: list,
    wiki_tools: WikiTools,
    max_turns: int,
    show_thinking: bool,
    live: "Live",
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    final_text = ""

    for _ in range(max_turns):
        response = client.messages.create(  # type: ignore[call-overload]
            model=model,
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        turn_text = ""
        tool_uses = []

        for block in response.content:
            if block.type == "thinking" and show_thinking:
                thinking_text = block.thinking  # type: ignore[attr-defined]
                console.print(Panel(
                    thinking_text[:500] + ("..." if len(thinking_text) > 500 else ""),
                    title="[dim]Thinking[/dim]",
                    border_style="dim",
                ))
            elif block.type == "text":
                turn_text += block.text  # type: ignore[attr-defined]
            elif block.type == "tool_use":
                tool_uses.append(block)

        if tool_uses:
            live.update(Panel(
                "Using: " + ", ".join(f"[cyan]{t.name}[/cyan]" for t in tool_uses),  # type: ignore[attr-defined]
                border_style="cyan",
            ))

        messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]

        if response.stop_reason == "end_turn" or response.stop_reason != "tool_use":
            final_text = turn_text
            break

        tool_results = []
        for t in tool_uses:
            result = wiki_tools.execute_tool(t.name, t.input)  # type: ignore[attr-defined]
            if len(result) > 20000:
                result = result[:20000] + "\n[... truncated ...]"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": t.id,  # type: ignore[attr-defined]
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})  # type: ignore[arg-type]

    return final_text


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

def _anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI function-calling format."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return result


def _run_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list,
    tools: list,
    wiki_tools: WikiTools,
    max_turns: int,
    live: "Live",
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    openai_tools = _anthropic_tools_to_openai(tools)
    final_text = ""

    # Prepend system message
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            max_tokens=8096,
            tools=openai_tools,  # type: ignore[arg-type]
            tool_choice="auto",
            messages=full_messages,  # type: ignore[arg-type]
        )

        choice = response.choices[0]
        message = choice.message
        turn_text = message.content or ""
        tool_calls = message.tool_calls or []

        if tool_calls:
            live.update(Panel(
                "Using: " + ", ".join(
                    f"[cyan]{tc.function.name}[/cyan]"  # type: ignore[union-attr]
                    for tc in tool_calls
                ),
                border_style="cyan",
            ))

        # Append assistant turn (include tool_calls if present)
        assistant_msg: dict = {"role": "assistant", "content": message.content}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,  # type: ignore[union-attr]
                        "arguments": tc.function.arguments,  # type: ignore[union-attr]
                    },
                }
                for tc in tool_calls
            ]
        full_messages.append(assistant_msg)

        if choice.finish_reason == "stop" or not tool_calls:
            final_text = turn_text
            break

        # Execute tools
        for tc in tool_calls:
            fn = tc.function  # type: ignore[union-attr]
            try:
                input_data = json.loads(fn.arguments)
            except json.JSONDecodeError:
                input_data = {}
            result = wiki_tools.execute_tool(fn.name, input_data)
            if len(result) > 20000:
                result = result[:20000] + "\n[... truncated ...]"
            full_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return final_text


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def run_agent(
    wiki_root: Path,
    system_prompt: str,
    user_message: str,
    *,
    max_turns: int = 40,
    show_thinking: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """
    Run the agentic loop with the configured provider (anthropic or openai).
    Returns the final text response.
    """
    cfg = get_provider_config()
    resolved_provider = provider or cfg["provider"]
    resolved_model = model or cfg.get("model") or DEFAULT_MODELS[resolved_provider]
    api_key = cfg["api_key"]

    wiki_tools = WikiTools(wiki_root)
    anthropic_tools = wiki_tools.get_tool_definitions()

    messages: list = [{"role": "user", "content": user_message}]

    with Live(console=console, refresh_per_second=4) as live:
        live.update(Panel(
            f"[bold cyan]Thinking...[/bold cyan] [dim]({resolved_provider} / {resolved_model})[/dim]",
            border_style="cyan",
        ))

        if resolved_provider == "anthropic":
            result = _run_anthropic(
                api_key=api_key,
                model=resolved_model,
                system_prompt=system_prompt,
                messages=messages,
                tools=anthropic_tools,
                wiki_tools=wiki_tools,
                max_turns=max_turns,
                show_thinking=show_thinking,
                live=live,
            )
        elif resolved_provider == "openai":
            result = _run_openai(
                api_key=api_key,
                model=resolved_model,
                system_prompt=system_prompt,
                messages=messages,
                tools=anthropic_tools,
                wiki_tools=wiki_tools,
                max_turns=max_turns,
                live=live,
            )
        else:
            raise ValueError(f"Unknown provider: {resolved_provider!r}. Use 'anthropic' or 'openai'.")

        live.update(Panel("[bold green]Done.[/bold green]", border_style="green"))

    return result


# ---------------------------------------------------------------------------
# Prompt builders (provider-agnostic)
# ---------------------------------------------------------------------------

def build_ingest_prompt(wiki_root: Path, source_path: Path) -> tuple[str, str]:
    schema = (wiki_root / "schema.md").read_text()
    source_content = source_path.read_text(encoding="utf-8", errors="replace")

    system = f"""\
You are a wiki maintainer. You build and maintain a structured knowledge base (wiki) \
from source documents. You write and update wiki pages — the human never edits the wiki directly.

The wiki schema and conventions are defined in schema.md:

{schema}

Your job: ingest the provided source document into the wiki by:
1. Writing a summary page in wiki/sources/
2. Creating or updating entity pages in wiki/entities/
3. Creating or updating concept pages in wiki/concepts/
4. Updating wiki/index.md
5. Appending to wiki/log.md

Be thorough. A good ingest touches 5-15 wiki pages with rich cross-references.
After all file operations are complete, give a brief summary of what you did.
"""

    user = f"""\
Please ingest the following source document into the wiki.

Source file: {source_path.name}

---

{source_content}
"""
    return system, user


def build_query_prompt(wiki_root: Path, question: str, output_format: str) -> tuple[str, str]:
    schema = (wiki_root / "schema.md").read_text()

    format_instructions = {
        "markdown": "Write your answer as a well-structured markdown document.",
        "table": "Present your answer primarily as a markdown comparison table.",
        "marp": (
            "Present your answer as a Marp slide deck. "
            "Start with `---\\nmarp: true\\n---` and use `---` to separate slides."
        ),
    }.get(output_format, "Write your answer as a well-structured markdown document.")

    system = f"""\
You are a wiki researcher. You answer questions by researching the wiki — \
reading the index, finding relevant pages, and synthesizing answers.

The wiki schema is:

{schema}

When answering:
1. Read wiki/index.md first to find relevant pages
2. Read relevant pages in full (search_wiki can help find them)
3. Synthesize a clear, well-cited answer
4. If the answer would make a good permanent wiki page, write it to wiki/concepts/
5. Append an entry to wiki/log.md
6. {format_instructions}

Your final response should be the answer itself (markdown, table, or marp as requested).
"""

    user = f"Question: {question}"
    return system, user


def build_lint_prompt(wiki_root: Path) -> tuple[str, str]:
    schema = (wiki_root / "schema.md").read_text()

    system = f"""\
You are a wiki auditor. You perform health checks on the wiki to find issues \
and improve overall data quality.

The wiki schema is:

{schema}

Check for:
- Contradictions between pages
- Orphan pages (no inbound links from other wiki pages)
- Missing cross-references (entity/concept mentioned on a page but no link)
- Important concepts mentioned across multiple pages but lacking their own page
- Stale or vague claims that could be more specific
- index.md entries missing or outdated

After reviewing, produce a structured lint report. Optionally fix issues directly.
Append a lint entry to wiki/log.md when done.
"""

    user = "Please run a health check on the wiki and produce a lint report."
    return system, user

# wiki-builder

A CLI tool that uses LLMs to build and maintain personal knowledge bases. Drop in source documents, and the LLM compiles them into a structured, interlinked wiki of markdown files — summaries, entity pages, concept pages, cross-references, and a running index. Ask questions against the wiki and get synthesized answers. Run health checks to keep everything consistent.

The wiki is a directory of markdown files you can open in Obsidian, VS Code, or any text editor. The LLM writes all of it. You never touch the wiki directly.

---

## How it works

Most LLM document tools (RAG, NotebookLM, ChatGPT file uploads) re-derive knowledge from scratch on every query. Nothing accumulates.

This tool does something different: when you add a source, the LLM reads it and **integrates it into a persistent wiki** — updating entity pages, writing concept summaries, noting where new data contradicts old claims, and maintaining cross-references. By the time you ask a question, the synthesis is already done. The wiki compounds with every source you add and every question you ask.

```
raw/                  ← you drop source documents here (immutable)
├── paper.md
├── article.md
└── assets/

wiki/                 ← LLM writes and maintains everything here
├── index.md          ← master catalog of all pages (auto-updated)
├── log.md            ← append-only operation log
├── sources/          ← one summary page per source document
├── concepts/         ← concept and topic pages
└── entities/         ← people, organizations, products, events

schema.md             ← conventions and workflows the LLM follows
```

The LLM runs as an agent with five file operation tools (`read_file`, `write_file`, `append_to_file`, `list_directory`, `search_wiki`). It uses these tools to read the schema, explore the existing wiki, and write or update pages — typically touching 5–15 files per ingest. You watch the tool calls stream in real time.

---

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/yourname/wiki-builder
cd wiki-builder
pip install -e .
```

This installs the `wiki` command globally.

**Dependencies:** `anthropic`, `openai`, `typer`, `rich`

---

## Setup

Set your API key as an environment variable:

```bash
# For Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...

# For OpenAI
export OPENAI_API_KEY=sk-...
```

Or save it permanently:

```bash
wiki config --provider anthropic --api-key sk-ant-...
wiki config --provider openai --api-key sk-...
```

---

## Quickstart

```bash
# 1. Create a new wiki
wiki init my-research/ --name "AI Research"

# 2. Add source documents to raw/
cp ~/papers/attention-is-all-you-need.md my-research/raw/

# 3. Ingest a source (LLM reads it and updates the wiki)
cd my-research
wiki ingest raw/attention-is-all-you-need.md

# 4. Ask questions
wiki query "what is self-attention and why does it matter?"

# 5. Check the wiki's health
wiki lint

# 6. See stats
wiki status
```

---

## Commands

### `wiki init <path>`

Scaffolds a new wiki project.

```bash
wiki init my-research/
wiki init my-research/ --name "ML Paper Notes"
```

Creates:
```
my-research/
├── schema.md          # LLM conventions (edit this to customize behavior)
├── .gitignore
├── raw/
│   └── assets/
└── wiki/
    ├── index.md
    ├── log.md
    ├── concepts/
    ├── entities/
    └── sources/
```

---

### `wiki ingest <source>`

Reads a source document and integrates it into the wiki. The LLM:
1. Writes a summary page in `wiki/sources/`
2. Creates or updates entity pages in `wiki/entities/`
3. Creates or updates concept pages in `wiki/concepts/`
4. Updates `wiki/index.md`
5. Appends an entry to `wiki/log.md`

```bash
wiki ingest raw/paper.md
wiki ingest raw/article.md --provider openai --model gpt-4o
wiki ingest raw/notes.md --thinking          # show Claude's reasoning
```

Supported source formats: any text file (`.md`, `.txt`, `.rst`, plain text). For PDFs, convert to markdown first (e.g. with `markitdown` or Obsidian Web Clipper).

---

### `wiki query "<question>"`

Asks a question against the wiki. The LLM reads the index, finds relevant pages, and synthesizes an answer.

```bash
wiki query "what is the transformer architecture?"
wiki query "compare attention mechanisms across these papers" --format table
wiki query "summarize everything I know about RLHF" --save
wiki query "what are the key open problems?" --output open-problems.md
```

**Options:**

| Flag | Description |
|------|-------------|
| `--format markdown` | Default. Well-structured markdown answer. |
| `--format table` | Answer as a comparison table. |
| `--format marp` | Marp slide deck (viewable in Obsidian with the Marp plugin). |
| `--save` | Files the answer back into the wiki as a new concept page. |
| `--output <file>` | Saves the answer to a file instead of printing. |

**Tip:** Use `--save` to make your queries compound in the wiki. Every good answer becomes a permanent page, enriching future queries.

---

### `wiki lint`

Runs a health check over the entire wiki and produces a report.

```bash
wiki lint
wiki lint --fix          # automatically fix issues found
```

Checks for:
- Orphan pages (no inbound links from other pages)
- Missing cross-references (entity mentioned but not linked)
- Contradictions between pages
- Concepts mentioned across multiple pages but lacking their own page
- Stale or vague claims
- `index.md` entries missing or out of date

---

### `wiki status`

Shows a summary of the wiki without calling the LLM.

```bash
wiki status
```

```
╭─────────────── Wiki Status ───────────────╮
│ Wiki: /home/user/my-research              │
│                                           │
│   📄 Sources:  12 pages                  │
│   💡 Concepts: 34 pages                  │
│   👤 Entities: 18 pages                  │
│   📁 Raw files: 12                       │
│   📝 Total wiki words: 47,203            │
╰───────────────────────────────────────────╯
```

---

### `wiki config`

Manages global settings stored in `~/.wiki-builder/config.json`.

```bash
wiki config --provider anthropic --api-key sk-ant-...
wiki config --provider openai --api-key sk-...
wiki config --model gpt-4o-mini              # set a default model
wiki config --show                           # print current config
```

---

## Provider support

Both Anthropic and OpenAI are supported. The provider can be set globally or overridden per command.

| Provider | Default model | Notes |
|----------|--------------|-------|
| `anthropic` | `claude-opus-4-6` | Default. Supports `--thinking` for extended reasoning. |
| `openai` | `gpt-4o` | Full tool use support. `--thinking` flag has no effect. |

**Resolution order** (highest to lowest priority):

1. `--provider` / `--model` CLI flags
2. `WIKI_PROVIDER` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` environment variables
3. Saved config (`~/.wiki-builder/config.json`)
4. Default: `anthropic` / `claude-opus-4-6`

**Examples:**

```bash
# Use OpenAI for a single command
wiki ingest raw/paper.md --provider openai

# Use a cheaper model for quick queries
wiki query "what is X?" --provider openai --model gpt-4o-mini

# Switch default provider
wiki config --provider openai

# Per-session override via env var
WIKI_PROVIDER=openai wiki ingest raw/paper.md
```

---

## Schema

`schema.md` is the configuration file that tells the LLM how to behave. It defines:

- Directory structure and what goes where
- Page format and frontmatter conventions
- Cross-linking rules
- The ingest, query, and lint workflows
- File naming conventions

The LLM reads `schema.md` at the start of every operation. You can edit it to change how the wiki is structured — for example, adding a `timeline/` directory, requiring specific frontmatter fields, or changing how entities are categorized.

This is the key file for customizing behavior. The defaults work well for research wikis, but different domains (a book, a codebase, a company's internal knowledge) may want different structures.

---

## Project structure

```
wiki-builder/
├── pyproject.toml               # package metadata and dependencies
└── wiki_builder/
    ├── __init__.py
    ├── cli.py                   # typer CLI — all commands live here
    ├── agent.py                 # agentic loop + provider backends + prompt builders
    ├── tools.py                 # file operation tools the LLM calls
    ├── config.py                # API key and provider resolution
    └── templates.py             # default schema.md, index.md, log.md content
```

### `cli.py`
Typer commands (`init`, `ingest`, `query`, `lint`, `status`, `config`). Resolves the wiki root, builds prompts, calls `run_agent`, and prints results.

### `agent.py`
The core of the tool. Contains:
- `run_agent()` — unified entry point that dispatches to the right provider backend
- `_run_anthropic()` — Anthropic agentic loop using the Messages API with tool use
- `_run_openai()` — OpenAI agentic loop using the Chat Completions API with function calling
- `build_ingest_prompt()`, `build_query_prompt()`, `build_lint_prompt()` — prompt builders

The loop runs until the model stops calling tools (`end_turn` / `finish_reason: stop`), up to a configurable `max_turns` (default: 40).

### `tools.py`
Five tools the LLM can call to interact with the filesystem:

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read any file relative to wiki root |
| `write_file(path, content)` | Write or overwrite a file (creates parent dirs) |
| `append_to_file(path, content)` | Append to a file (used for `log.md`) |
| `list_directory(path)` | List files and subdirectories |
| `search_wiki(query)` | Grep all wiki `.md` files for a term, returns matching paths |

All paths are validated to prevent directory traversal outside the wiki root.

Tool definitions are stored in Anthropic format and converted to OpenAI's function-calling format automatically when using the OpenAI backend.

### `config.py`
Handles provider and API key resolution. Saves config to `~/.wiki-builder/config.json`. Supports legacy `ANTHROPIC_API_KEY` as well as the newer per-provider key names.

### `templates.py`
The default content written by `wiki init`: `schema.md` (the LLM's behavioral spec), and empty stubs for `index.md` and `log.md`.

---

## Workflow tips

**Use Obsidian as your frontend.** Open the wiki root as an Obsidian vault. The graph view shows the shape of your knowledge — what's connected, what's isolated. Use the Dataview plugin to query frontmatter. Use Marp for slide output.

**Ingest sources one at a time.** The LLM does a better job when you ingest sources one at a time and stay involved — reading the summaries, checking the updates, noting what to emphasize next time.

**Use `--save` on queries you care about.** Every good answer filed back into the wiki is available for future queries and makes the synthesis richer.

**Edit `schema.md` as you go.** If the LLM is creating pages in a format you don't like, edit `schema.md` to change the convention. The LLM will follow the updated schema on the next operation.

**Keep raw/ immutable.** The LLM is instructed never to modify `raw/`. It's your source of truth. If you want to re-ingest a source with different instructions, update `schema.md` and run `wiki ingest` again.

**The wiki is a git repo.** Run `git init` in the wiki root. Every ingest, query, and lint pass produces a natural commit point. You get full history, easy rollback, and the ability to branch experiments.

```bash
cd my-research
git init
git add .
git commit -m "init wiki"
wiki ingest raw/paper.md
git add -A && git commit -m "ingest: attention is all you need"
```

---

## Limitations

- **Source format:** Only plain text sources are supported natively. Convert PDFs, DOCX, etc. to markdown before ingesting.
- **Scale:** The index-based navigation works well up to ~100–200 sources. Beyond that, consider adding a search tool (e.g. [qmd](https://github.com/tobi/qmd)) and pointing the LLM at it.
- **Images:** The LLM reads markdown but won't automatically process inline images from sources. Download images locally (Obsidian's "Download attachments" hotkey helps) and reference them by path. The LLM can be asked to view specific images separately.
- **Cost:** Each ingest touches 5–15 files and may run 10–20 tool call turns. With Claude Opus 4.6, a typical ingest costs $0.05–0.20 depending on source length and wiki size. Use `--model claude-sonnet-4-6` or `--model gpt-4o-mini` to reduce cost.

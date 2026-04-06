SCHEMA_TEMPLATE = """\
# Wiki Schema

This document defines the structure, conventions, and workflows for this wiki.
The LLM reads this file at the start of every session to understand how to maintain the wiki.

## Directory Structure

```
raw/          — Immutable source documents. Never modify files here.
raw/assets/   — Downloaded images and media.
wiki/         — You own this layer entirely. Read, write, and maintain everything here.
  index.md    — Master catalog of all wiki pages (update on every ingest).
  log.md      — Append-only operation log (append on every operation).
  concepts/   — Concept and topic pages (ideas, theories, frameworks).
  entities/   — Entity pages (people, places, organizations, products, events).
  sources/    — One summary page per source document.
```

## Page Conventions

### Frontmatter
Every wiki page should start with YAML frontmatter:
```yaml
---
title: Page Title
type: concept | entity | source
tags: [tag1, tag2]
sources: [source-slug-1, source-slug-2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Cross-references
Use standard markdown links: `[[Page Title]]` style or `[Page Title](../concepts/page-title.md)`.
Always link to related pages. More links = better wiki.

### Page structure
- Start with a 1-2 sentence summary (this is what appears in index.md)
- Use ## headers for major sections
- Use bullet points for lists of facts, attributes, or examples
- End with a ## Related section listing linked pages

## index.md Format

```markdown
# Wiki Index

## Sources
| Page | Summary | Date |
|------|---------|------|
| [Title](sources/slug.md) | One-line summary | YYYY-MM-DD |

## Concepts
| Page | Summary |
|------|---------|
| [Title](concepts/slug.md) | One-line summary |

## Entities
| Page | Summary |
|------|---------|
| [Title](entities/slug.md) | One-line summary |
```

## log.md Format

Each entry must start with this prefix pattern for easy grep/parsing:
```
## [YYYY-MM-DD] operation | title
```

Operations: `ingest`, `query`, `lint`, `update`

## Ingest Workflow

When ingesting a source document:
1. Read the source file thoroughly
2. Write a summary page in `wiki/sources/` (slug = kebab-case title)
3. Identify all entities mentioned → create or update pages in `wiki/entities/`
4. Identify all concepts → create or update pages in `wiki/concepts/`
5. Update `wiki/index.md` with the new source and any new entity/concept pages
6. Append an entry to `wiki/log.md`
7. Add cross-references: link the source page to entity/concept pages and vice versa

A single source should touch 5-15 wiki pages. Be thorough with cross-references.

## Query Workflow

When answering a query:
1. Read `wiki/index.md` to find relevant pages
2. Read those pages in full
3. Synthesize a clear answer with citations to wiki pages
4. If the answer would be useful as a permanent wiki page, create it in `wiki/concepts/`
5. Append an entry to `wiki/log.md`

## Lint Workflow

When linting the wiki:
1. Read all pages in the wiki
2. Check for: contradictions between pages, orphan pages (no inbound links),
   missing cross-references, stale or vague claims, concepts mentioned but lacking their own page
3. Produce a lint report with specific issues and suggested fixes
4. Optionally fix issues directly

## Naming Conventions

- File slugs: lowercase, hyphens, no spaces (e.g., `neural-networks.md`)
- Entity pages: named after the entity (e.g., `geoffrey-hinton.md`)
- Concept pages: named after the concept (e.g., `backpropagation.md`)
- Source pages: named after the source title (e.g., `attention-is-all-you-need.md`)
"""

EMPTY_INDEX = """\
# Wiki Index

*No pages yet. Add sources with `wiki ingest <file>`.*

## Sources

| Page | Summary | Date |
|------|---------|------|

## Concepts

| Page | Summary |
|------|---------|

## Entities

| Page | Summary |
|------|---------|
"""

EMPTY_LOG = """\
# Wiki Log

*Append-only record of all wiki operations.*

"""

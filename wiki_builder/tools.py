"""
File operation tools that the LLM agent uses to read/write the wiki.
All paths are relative to the wiki root.
"""

import subprocess
from pathlib import Path


class WikiTools:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _resolve(self, path: str) -> Path:
        """Resolve a relative path against the wiki root, preventing traversal."""
        resolved = (self.root / path).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise ValueError(f"Path {path!r} escapes wiki root")
        return resolved

    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.exists():
            return f"[File not found: {path}]"
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path}"

    def append_to_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended to: {path}"

    def list_directory(self, path: str = ".") -> str:
        p = self._resolve(path)
        if not p.exists():
            return f"[Directory not found: {path}]"
        entries = []
        for item in sorted(p.iterdir()):
            prefix = "📁 " if item.is_dir() else "📄 "
            entries.append(f"{prefix}{item.name}")
        return "\n".join(entries) if entries else "[empty directory]"

    def search_wiki(self, query: str) -> str:
        """Simple grep over all wiki .md files."""
        wiki_dir = self._resolve("wiki")
        if not wiki_dir.exists():
            return "[wiki/ directory not found]"
        try:
            result = subprocess.run(
                ["grep", "-r", "-i", "-l", "--include=*.md", query, str(wiki_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if not result.stdout.strip():
                return f"[No wiki pages found matching: {query!r}]"
            # Return relative paths
            lines = []
            for line in result.stdout.strip().splitlines():
                rel = Path(line).relative_to(self.root)
                lines.append(str(rel))
            return "\n".join(lines)
        except Exception as e:
            return f"[Search error: {e}]"

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "read_file",
                "description": (
                    "Read a file from the wiki project. "
                    "Path is relative to the wiki root (e.g., 'wiki/index.md', "
                    "'raw/my-article.md', 'schema.md')."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"}
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": (
                    "Write content to a file (creates or overwrites). "
                    "Use this to create or update wiki pages. "
                    "Path is relative to the wiki root."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "append_to_file",
                "description": (
                    "Append content to a file without overwriting it. "
                    "Use this for wiki/log.md to add log entries."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                        "content": {"type": "string", "description": "Content to append"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": (
                    "List files and directories at a path. "
                    "Useful for seeing what wiki pages exist. "
                    "Path is relative to the wiki root. Defaults to root."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path (default: '.')",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "search_wiki",
                "description": (
                    "Search all wiki markdown files for a keyword or phrase. "
                    "Returns a list of matching file paths. "
                    "Use this to find relevant pages before reading them."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term or phrase",
                        }
                    },
                    "required": ["query"],
                },
            },
        ]

    def execute_tool(self, name: str, input_data: dict) -> str:
        if name == "read_file":
            return self.read_file(input_data["path"])
        elif name == "write_file":
            return self.write_file(input_data["path"], input_data["content"])
        elif name == "append_to_file":
            return self.append_to_file(input_data["path"], input_data["content"])
        elif name == "list_directory":
            return self.list_directory(input_data.get("path", "."))
        elif name == "search_wiki":
            return self.search_wiki(input_data["query"])
        else:
            return f"[Unknown tool: {name}]"

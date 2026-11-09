from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .catalog import Catalog, WORKFLOW


def create_server(data: Path) -> MCPServer:
    catalog = Catalog(data)
    server = MCPServer(
        "ProbablySage", version="0.1.0",
        instructions="Local Probably Stolen source evidence. " + WORKFLOW,
    )
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=readonly)
    def doctor() -> dict:
        """FIRST call: check installed assembly freshness, indexed coverage and limitations."""
        return catalog.doctor()

    @server.tool(annotations=readonly)
    def search_symbols(query: str, limit: int = 10, offset: int = 0) -> dict:
        """Find real C# types/methods/fields. Use a short name. Returns IDs and exact signatures.
        Next: read_symbol(symbol_id). limit 1-50. Use next_offset for more overloads."""
        return catalog.symbols(query, limit, offset)

    @server.tool(annotations=readonly)
    def read_symbol(symbol_id: int, count: int = 100) -> dict:
        """Read a declaration and body using an ID returned by search_symbols.
        At most 120 lines; continue via read_lines(file_id, next_line)."""
        return catalog.symbol(symbol_id, count)

    @server.tool(annotations=readonly)
    def search_source(query: str, corpus: Literal["all", "game", "source", "official"] = "all",
                      limit: int = 10, offset: int = 0) -> dict:
        """Literal text search, NOT regex. Search item IDs, hooks, tags or code fragments.
        Returns file_id and line; then read_lines for guards and surrounding code."""
        return catalog.search(query, corpus, limit, offset)

    @server.tool(annotations=readonly)
    def read_lines(file_id: int, start_line: int = 1, count: int = 60) -> dict:
        """Read indexed evidence by discovered file_id, never a guessed filesystem path.
        Lines start at 1. count 1-120. Follow next_line if output is truncated."""
        return catalog.read(file_id, start_line, count)

    @server.tool(annotations=readonly)
    def find_references(member: str, limit: int = 10, offset: int = 0) -> dict:
        """Find syntax calls/member accesses by SHORT exact name, e.g. BuyItem.
        NOT a resolved call graph: verify receiver type and read each caller's guards."""
        return catalog.references(member, limit, offset)

    @server.tool(annotations=readonly)
    def search_official_docs(query: str, limit: int = 10, offset: int = 0) -> dict:
        """Search locally cached OFFICIAL Chinese API/migration/rules docs.
        Uses the pinned commit from setup. Search one term at a time; read_lines for context."""
        return catalog.search(query, "official", limit, offset)

    @server.tool(annotations=readonly)
    def development_guide(topic: str = "hooks") -> dict:
        """Get step-by-step research steps. Topics: items, inventory, dialogue, ui, save,
        hooks, patching, guns. Suggestions are not fabricated API guarantees."""
        return catalog.guide(topic)

    return server

"""Check real stdio transport against a locally built game index."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def payload(result):
    if result.is_error:
        raise RuntimeError("MCP tool returned an error: " + str(result.content))
    return json.loads(next(c.text for c in result.content if c.type == "text"))


async def run(data: Path):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "probablysage", "--data", str(data.resolve()), "serve"],
    )
    async with Client(parameters, read_timeout_seconds=30) as client:
        tools = await client.list_tools()
        state = payload(await client.call_tool("doctor", {}))
        assert not state["snapshot"]["stale"], "Rebuild the outdated index first"
        assert state["snapshot"]["has_installed_game_evidence"], "No installed game evidence"
        found = payload(await client.call_tool("search_symbols", {"query": "ReadModDataFileText"}))
        candidates = [hit for hit in found["matches"] if hit["qualified"] == "ModHelper.ReadModDataFileText"]
        assert candidates, "Expected API not found; check the installed game version"
        symbol = candidates[0]
        body = payload(await client.call_tool("read_symbol", {"symbol_id": symbol["symbol_id"]}))
        assert any("ReadAllText" in line["text"] for line in body["lines"]), "No actual implementation read"
        docs = payload(await client.call_tool("search_official_docs", {"query": "ReadModDataFileText"}))
        assert docs["matches"], "Official docs are missing"
        references = payload(await client.call_tool("find_references", {"member": "TryAcceptAll", "limit": 3}))
        assert references["references"], "No game call evidence"
        generic = payload(await client.call_tool("find_references", {"member": "GetComponent", "limit": 50}))
        assert any("GetComponent<" in hit["expression"] for hit in generic["references"]), "Generic call lookup failed"
        guide = payload(await client.call_tool("development_guide", {"topic": "ui"}))
        assert "EndOfDayTabletFrame" in guide["practice"]["content"], "Native UI practice is unavailable"
        practice = payload(await client.call_tool("search_source", {
            "query": "PixelWindow", "corpus": "practice",
        }))
        assert practice["matches"], "Bundled practice was not indexed"
        assert state["parser_issues"]["available"], "Parser issue locations are unavailable"
        print(json.dumps({
            "transport": "stdio", "tools": len(tools.tools),
            "files": state["counts"]["files"], "symbols": state["counts"]["symbols"],
            "references": state["counts"]["refs"], "parser_errors": state["parser_errors"],
            "official_commit": state["snapshot"]["official_commit"],
            "signature": symbol["signature"],
            "read_implementation": True, "official_doc_hits": len(docs["matches"]),
            "game_reference_hits": len(references["references"]),
            "generic_reference_hits": len(generic["references"]),
            "ui_practice_available": True,
            "parser_locations": len(state["parser_issues"]["issues"]),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path.home() / ".probablysage")
    asyncio.run(run(parser.parse_args().data))

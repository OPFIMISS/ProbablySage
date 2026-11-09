from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from subprocess import SubprocessError


def configuration(data: Path) -> dict:
    return {"mcpServers": {"probablysage": {
        "command": str(Path(sys.executable).resolve()),
        "args": ["-m", "probablysage", "--data", str(data.resolve()), "serve"],
    }}}


def main():
    parser = argparse.ArgumentParser(description="ProbablySage local source research MCP")
    parser.add_argument("--data", type=Path, default=Path.home() / ".probablysage",
                        help="Private local index directory; never place inside a public repository")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="Decompile locally and atomically build the query index")
    setup.add_argument("--game", type=Path)
    setup.add_argument("--source", type=Path, action="append", default=[],
                       help="Additional authorized C# source directory; repeatable")
    setup.add_argument("--ilspy", help="Optional absolute path to ilspycmd")
    setup.add_argument("--skip-docs", action="store_true", help="Offline setup without official docs")
    commands.add_parser("serve", help="Read-only MCP over stdio; does not launch the game")
    commands.add_parser("doctor", help="Print snapshot coverage and freshness")
    commands.add_parser("config", help="Print MCP JSON and write local JSON/TOML examples")
    args = parser.parse_args()
    args.data = args.data.resolve()
    try:
        if args.command == "setup":
            from .index import build
            metadata = build(args.data, args.game, args.source, args.ilspy, args.skip_docs)
            print(json.dumps({key: value for key, value in metadata.items()
                              if key != "source_files"}, ensure_ascii=False, indent=2))
            write_config(args.data)
        elif args.command == "serve":
            from .server import create_server
            # Fail before opening stdio if the index is missing or unreadable.
            from .catalog import Catalog
            Catalog(args.data).doctor()
            create_server(args.data).run(transport="stdio")
        elif args.command == "doctor":
            from .catalog import Catalog
            print(json.dumps(Catalog(args.data).doctor(), ensure_ascii=False, indent=2))
        else:
            write_config(args.data)
    except (ValueError, OSError, TimeoutError, SubprocessError) as error:
        print(f"ProbablySage: {error}", file=sys.stderr)
        raise SystemExit(1) from None


def write_config(data: Path):
    data.mkdir(parents=True, exist_ok=True)
    config = configuration(data)
    text = json.dumps(config, ensure_ascii=False, indent=2)
    (data / "mcp.local.json").write_text(text + "\n", encoding="utf-8")
    server = config["mcpServers"]["probablysage"]
    toml = ("[mcp_servers.probablysage]\n"
            f"command = {json.dumps(server['command'], ensure_ascii=False)}\n"
            f"args = {json.dumps(server['args'], ensure_ascii=False)}\n")
    (data / "codex.local.toml").write_text(toml, encoding="utf-8")
    print(text)
    print(f"\nLocal client examples: {data / 'mcp.local.json'} and {data / 'codex.local.toml'}")

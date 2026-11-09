# Agent Entry

Read README.md, then docs/AGENT_GUIDE.zh-CN.md. The user's request takes precedence.

## Installing For A User

1. Find the user's real game folder, Python 3.10+, .NET SDK and this checkout.
2. Run setup.ps1 with the real game folder; on other platforms use the documented Python commands.
3. Read the generated local mcp.local.json or codex.local.toml. Use absolute paths.
4. Register ONLY the probablysage entry in the client's existing configuration. Preserve every other entry and setting. If the client's configuration format is unknown, give the generated entry and state what remains.
5. Restart/reconnect the client's MCP connection when needed. Call doctor through MCP and search/read one real symbol.
6. Report what actually worked. Do not say the MCP is connected merely because pip install or index creation succeeded.

## Source And Publishing

- No game DLLs, decompiled sources, official-document caches, SQLite indexes, local paths, credentials or user Mods in commits.
- Local indexing is authorized by setup input. Do not upload source to a hosted service.
- Do not launch the game, alter saves, approve Mods, patch protection code or configure game automation.
- Query tools are read-only. Changes to setup/index generation belong in the explicit CLI.
- No eval, dynamically supplied code, arbitrary reflection or arbitrary file-read tool.
- Tests should check evidence boundaries and protocol behavior, not mirror implementation.
- Use the official MCP Python SDK; diagnostics belong on stderr during stdio serving.

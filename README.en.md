# ProbablySage

Local **Probably Stolen** source and official modding documentation MCP.

Give a local tool-enabled Agent:

> Install this MCP project: https://github.com/OPFIMISS/ProbablySage . My game directory is `D:/Steam/steamapps/common/Probably Stolen`. Read README.md and docs/AGENT_GUIDE.zh-CN.md. Run setup, merge only the generated probablysage client entry, reconnect, call doctor, and search/read one real method. Preserve other settings. Do not launch the game or modify saves.

Requirements: Python 3.10+, Git, an installed game, and the .NET 10 SDK. The pinned ILSpy tool targets .NET 10; alternatively supply an already working ILSpy executable with `--ilspy`.

```powershell
git clone https://github.com/OPFIMISS/ProbablySage.git C:/Projects/ProbablySage
cd C:/Projects/ProbablySage
.\setup.ps1 -GamePath 'D:/Steam/steamapps/common/Probably Stolen'
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e .
.\.venv\Scripts\python.exe -m probablysage setup --game 'D:/Steam/steamapps/common/Probably Stolen'
```

On Linux/macOS use `.venv/bin/python`; the installed game layout and ability to run ILSpy must match. These platforms are not validated.

Setup decompiles installed `Assembly-CSharp` and, if present, `Assembly-CSharp-firstpass`; builds a Tree-sitter C# declaration/reference index; downloads pinned Chinese official docs; and generates absolute-path MCP JSON and Codex TOML snippets. Default private data: `~/.probablysage`. Merge the entry into your client's existing configuration, preserving other settings.

Tools: `doctor`, `search_symbols`, `read_symbol`, `search_source`, `read_lines`, `find_references`, `search_official_docs`, `development_guide`.

Start with `doctor`, search official docs, discover a symbol ID, read its implementation, then inspect callers and guards. References are syntactic matches, not resolved dispatch. Results include origins, line numbers, freshness and pagination. Rebuild after game updates.

**0.1.1 development preview.** Generic calls such as `GetComponent<T>()` are now discoverable by their short member name. Parser issues include file IDs and line locations. Rebuild the index after upgrading.

`development_guide(topic="ui")` also returns the bundled [native UI integration practice](src/probablysage/practice/native-ui.md), covering original tablet frames, scene anchoring, inventory alignment, native highlighting and lifecycle pitfalls. Topics `scene`, `inventory` and `highlight` include it too. Search with `corpus="practice"`; community practice is explicitly distinguished from official documentation and installed game evidence.

No game runtime Agent, headless testing, arbitrary file access or code execution. No game source/binaries/assets are distributed or uploaded by the server. Your chosen MCP client may transmit returned context to its model provider. Freshness uses size/mtime rather than hashes.

Official API support and restrictions: [probably-stolen-modding](https://github.com/dragonpan2/probably-stolen-modding). Actual installed signatures take precedence over assumptions. Inspired by [RimSage](https://github.com/realloon/RimSage); independently implemented using the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

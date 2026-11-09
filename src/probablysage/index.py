"""Build a local snapshot. No game code is included in the distribution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone

import tree_sitter_c_sharp
from tree_sitter import Language, Parser

from . import __version__

PRACTICE_ROOT = Path(__file__).parent / "practice"
OFFICIAL_REPO = "dragonpan2/probably-stolen-modding"
OFFICIAL_FILES = (
    "README.zh-CN.md", "ModdingGuide.zh-CN.md", "APIChanges.zh-CN.md",
    "CodeOfConduct.zh-CN.md",
)
DECLARATIONS = {
    "class_declaration", "struct_declaration", "interface_declaration",
    "enum_declaration", "record_declaration", "method_declaration",
    "constructor_declaration", "property_declaration", "event_declaration",
    "delegate_declaration",
}
TYPES = {
    "class_declaration", "struct_declaration", "interface_declaration",
    "enum_declaration", "record_declaration",
}


def stamp(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def fetch_json(url: str):
    return json.loads(fetch(url))


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ProbablySage/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError("Official document is larger than the download limit")
    return data.decode("utf-8-sig")


def ensure_ilspy(data: Path, supplied: str | None) -> str:
    if supplied:
        tool = Path(supplied).resolve()
        if not tool.is_file():
            raise ValueError("The supplied ilspycmd executable does not exist")
        return str(tool)
    installed = shutil.which("ilspycmd")
    if installed:
        return installed
    tool = data / "tools" / ("ilspycmd.exe" if os.name == "nt" else "ilspycmd")
    if not tool.is_file():
        if not shutil.which("dotnet"):
            raise ValueError("Install the .NET 10 SDK, or supply --ilspy with a working ilspycmd")
        subprocess.run(
            ["dotnet", "tool", "install", "ilspycmd", "--tool-path", str(tool.parent),
             "--version", "11.0.0.9375"], check=True, timeout=180,
        )
    return str(tool)


def _schema(db: sqlite3.Connection):
    db.executescript("""
        CREATE TABLE files(
          id INTEGER PRIMARY KEY, corpus TEXT NOT NULL, path TEXT NOT NULL,
          origin TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL);
        CREATE TABLE lines(file_id INTEGER, line INTEGER, text TEXT,
          PRIMARY KEY(file_id,line));
        CREATE TABLE symbols(
          id INTEGER PRIMARY KEY, file_id INTEGER, name TEXT, qualified TEXT,
          kind TEXT, signature TEXT, start INTEGER, end INTEGER, parent_id INTEGER);
        CREATE INDEX symbols_name ON symbols(name);
        CREATE TABLE refs(
          file_id INTEGER, line INTEGER, name TEXT, expression TEXT, kind TEXT,
          caller_id INTEGER);
        CREATE INDEX refs_name ON refs(name);
        CREATE TABLE parse_issues(
          file_id INTEGER, start INTEGER, end INTEGER, kind TEXT, excerpt TEXT);
        CREATE INDEX parse_issues_file ON parse_issues(file_id);
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
    """)


def _text(node, raw: bytes) -> str:
    return raw[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _name(node, raw: bytes) -> str:
    child = node.child_by_field_name("name")
    return _text(child, raw) if child else ""


def _member_name(node, raw: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return _member_name(name, raw)
    if node.type == "generic_name":
        identifier = next((c for c in node.named_children if c.type == "identifier"), None)
        if identifier is not None:
            return _text(identifier, raw)
    return _text(node, raw)


def index_file(db, parser, path: Path, corpus: str, origin: str, relative: str) -> int:
    raw = path.read_bytes()
    if len(raw) > 32_000_000:
        raise ValueError(f"Source file too large: {relative}")
    info = stamp(path)
    file_id = db.execute(
        "INSERT INTO files(corpus,path,origin,size,mtime_ns) VALUES(?,?,?,?,?)",
        (corpus, relative, origin, info["size"], info["mtime_ns"]),
    ).lastrowid
    text = raw.decode("utf-8-sig")
    db.executemany("INSERT INTO lines VALUES(?,?,?)",
                   ((file_id, n, line) for n, line in enumerate(text.splitlines(), 1)))
    if path.suffix != ".cs":
        return 0
    tree = parser.parse(raw)
    parse_errors = 0

    def report(node):
        nonlocal parse_errors
        parse_errors += 1
        db.execute("INSERT INTO parse_issues VALUES(?,?,?,?,?)",
                   (file_id, node.start_point.row + 1, node.end_point.row + 1,
                    "missing:" + node.type if node.is_missing else "error",
                    _text(node, raw)[:200]))

    def visit(node, names: tuple[str, ...], parent_id: int | None):
        if node.type == "ERROR" or node.is_missing:
            report(node)
        for child in node.children:
            if child.is_missing and not child.is_named:
                report(child)
        next_names, owner = names, parent_id
        if node.type == "compilation_unit":
            file_namespace = next((c for c in node.named_children
                                   if c.type == "file_scoped_namespace_declaration"), None)
            if file_namespace is not None:
                next_names = names + (_name(file_namespace, raw),)
        if node.type in {"namespace_declaration", "file_scoped_namespace_declaration"}:
            next_names = names + (_name(node, raw),)
        if node.type in DECLARATIONS:
            name = _name(node, raw)
            body = node.child_by_field_name("body")
            # Types without a "body" field expose a declaration_list child.
            if body is None:
                body = next((c for c in node.named_children
                             if c.type in {"declaration_list", "enum_member_declaration_list",
                                           "accessor_list", "arrow_expression_clause"}), None)
            end = body.start_byte if body else node.end_byte
            signature = " ".join(raw[node.start_byte:end].decode("utf-8", errors="replace").split())
            owner = db.execute(
                "INSERT INTO symbols(file_id,name,qualified,kind,signature,start,end,parent_id) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (file_id, name, ".".join(names + (name,)), node.type.removesuffix("_declaration"),
                 signature[:8000], node.start_point.row + 1, node.end_point.row + 1, parent_id),
            ).lastrowid
            if node.type in TYPES:
                next_names = names + (name,)
        if node.type in {"field_declaration", "event_field_declaration"}:
            for declaration in node.named_children:
                if declaration.type == "variable_declaration":
                    for variable in declaration.named_children:
                        if variable.type == "variable_declarator":
                            name = _name(variable, raw)
                            db.execute(
                                "INSERT INTO symbols(file_id,name,qualified,kind,signature,start,end,parent_id) "
                                "VALUES(?,?,?,?,?,?,?,?)",
                                (file_id, name, ".".join(names + (name,)), "field",
                                 " ".join(_text(node, raw).split())[:8000],
                                 node.start_point.row + 1, node.end_point.row + 1, parent_id),
                            )
        if node.type == "invocation_expression":
            function = node.child_by_field_name("function")
            if function:
                name = _member_name(function, raw)
                db.execute("INSERT INTO refs VALUES(?,?,?,?,?,?)",
                           (file_id, node.start_point.row + 1, name[:500],
                            _text(function, raw)[:1000], "call", parent_id))
        elif node.type == "member_access_expression" and (
            node.parent is None or node.parent.type != "invocation_expression"
        ):
            db.execute("INSERT INTO refs VALUES(?,?,?,?,?,?)",
                       (file_id, node.start_point.row + 1, _member_name(node, raw)[:500],
                        _text(node, raw)[:1000], "member_access", parent_id))
        for child in node.named_children:
            visit(child, next_names, owner)

    visit(tree.root_node, (), None)
    return parse_errors


def build(data: Path, game: Path | None, sources: list[Path],
          ilspy: str | None = None, skip_docs: bool = False) -> dict:
    data = data.resolve()
    data.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=data) as temporary:
        work = Path(temporary)
        roots: list[tuple[Path, str, str]] = []
        assemblies = []
        if game:
            managed = game.resolve() / "Probably Stolen_Data" / "Managed"
            assembly = managed / "Assembly-CSharp.dll"
            if not assembly.is_file():
                raise ValueError("Not a Probably Stolen game folder: missing Probably Stolen_Data/Managed/Assembly-CSharp.dll")
            tool = ensure_ilspy(data, ilspy)
            for name in ("Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll"):
                dll = managed / name
                if not dll.is_file():
                    continue
                before = stamp(dll)
                destination = work / dll.stem
                result = subprocess.run(
                    [tool, "-p", "-o", str(destination), "-r", str(managed), str(dll)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                )
                if result.returncode:
                    raise ValueError("ILSpy failed: " + (result.stderr or result.stdout)[-3000:])
                if before != stamp(dll):
                    raise ValueError("Game updated while decompiling; rebuild the index")
                assemblies.append(before)
                roots.append((destination, "game", name))
        source_files = []
        for n, root in enumerate(sources):
            root = root.resolve()
            if not root.is_dir():
                raise ValueError(f"Source directory does not exist: {root}")
            roots.append((root, "source", f"source-{n + 1}"))
        commit = None
        if not skip_docs:
            commit = fetch_json(f"https://api.github.com/repos/{OFFICIAL_REPO}/commits/main")["sha"]
            if not re.fullmatch("[0-9a-f]{40}", commit):
                raise ValueError("Unexpected official documentation commit")
            docs = work / "official"
            docs.mkdir()
            for name in OFFICIAL_FILES:
                (docs / name).write_text(
                    fetch(f"https://raw.githubusercontent.com/{OFFICIAL_REPO}/{commit}/{name}"),
                    encoding="utf-8",
                )
            roots.append((docs, "official", f"https://github.com/{OFFICIAL_REPO}/blob/{commit}"))
        if not roots:
            raise ValueError("Supply --game or --source, or allow official document downloads")
        roots.append((PRACTICE_ROOT, "practice", "ProbablySage community practice (not official API)"))
        parser = Parser(Language(tree_sitter_c_sharp.language()))
        database = work / "index.sqlite3"
        db = sqlite3.connect(database)
        try:
            _schema(db)
            errors = 0
            for root, corpus, origin in roots:
                suffix = "*.md" if corpus in {"official", "practice"} else "*.cs"
                for path in sorted(root.rglob(suffix)):
                    resolved = path.resolve()
                    # Do not follow links outside the explicitly supplied source root.
                    if not resolved.is_relative_to(root.resolve()):
                        continue
                    relative = path.relative_to(root).as_posix()
                    if any(part in {".git", ".venv", "obj", "bin", "node_modules"}
                           for part in Path(relative).parts):
                        continue
                    errors += index_file(db, parser, resolved, corpus, origin, relative)
                    if corpus == "source":
                        source_files.append(stamp(resolved))
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                      for name in ("files", "symbols", "refs")}
            if game and not db.execute("SELECT 1 FROM symbols LIMIT 1").fetchone():
                raise ValueError("Decompilation produced no C# declarations")
            metadata = {
                "schema": 2, "builder_version": __version__,
                "built_utc": datetime.now(timezone.utc).isoformat(),
                "game": str(game.resolve()) if game else None, "assemblies": assemblies,
                "source_files": source_files, "source_roots": [str(p.resolve()) for p in sources],
                "official_commit": commit, "official_repo": OFFICIAL_REPO,
                "parse_errors": errors, "counts": counts,
                "practice_files": [stamp(path) for path in sorted(PRACTICE_ROOT.glob("*.md"))],
                "limitations": [
                    "References are syntax matches, not resolved C# dispatch or a complete call graph.",
                    "Decompiled C# can contain parser errors; read surrounding lines and check IL if ambiguous.",
                    "Game runtime, UI pixels, callbacks and save compatibility are not tested by this server.",
                    "Freshness uses file size and modification time, not content hashes.",
                ],
            }
            db.execute("INSERT INTO metadata VALUES('snapshot',?)",
                       (json.dumps(metadata, ensure_ascii=False),))
            db.commit()
        finally:
            db.close()
        # A failed rebuild leaves the previous snapshot intact.
        os.replace(database, data / "index.sqlite3")
        return metadata

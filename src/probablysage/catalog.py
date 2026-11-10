from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from . import __version__
from .index import PRACTICE_ROOT, stamp

WORKFLOW = (
    "1. Call doctor; if stale, ask the local Agent to run setup again. "
    "2. Search official docs for the feature and its supported lifecycle. "
    "3. Search symbols using a short exact type/method name. "
    "4. Read the returned symbol_id; do not invent a signature from its name. "
    "5. Find syntax references by its short member name, then read callers and guards. "
    "6. Edit only the target Mod. Build against these installed assemblies, scan using "
    "the official scanner, and distinguish compilation from in-game verification."
)
TOPICS = {
    "items": ("物品 生成 所有权 持久化", ["GameItem", "ModItemDirectory", "DirectoryMaster"]),
    "inventory": ("机器窗口 存档 溢出", ["GameGridInventory", "PixelWindow", "GraphUtils"]),
    "dialogue": ("对话 顾客", ["Dialogue", "DialogUIManager", "StoreClient"]),
    "ui": ("自定义 UI 生命周期", ["CustomUIManager", "CustomUIBuilder", "EndOfDayTabletFrame"]),
    "save": ("持久化 ModData", ["SaveFiles", "ModHelper", "PlayerStore"]),
    "hooks": ("生命周期 钩子", ["ModHook", "IMod", "ModHelper"]),
    "patching": ("反射 Harmony 能力", ["ModReflect", "ModHelper"]),
    "guns": ("枪械 顾客", ["StoreClientListGun", "GunOrderData", "Shotgun"]),
    "scene": ("场景 相机", ["StoreUIManager", "StoreClientCounter", "GameGridInventory"]),
    "highlight": ("库存 交互", ["Interactable", "GameSlotInventory", "HighlightManager"]),
    "network": ("AddNetworkUpgrade 人脉 升级 生命周期", ["ModHelper", "NetworkUpgrade", "ModHook"]),
}


class Catalog:
    def __init__(self, data: Path):
        self.data = data.resolve()
        self.database = self.data / "index.sqlite3"

    @contextmanager
    def open(self):
        if not self.database.is_file():
            raise ValueError("No index. Run setup first; see README.md.")
        db = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def metadata(db) -> dict:
        row = db.execute("SELECT value FROM metadata WHERE key='snapshot'").fetchone()
        if not row:
            raise ValueError("Invalid index: rebuild with setup")
        result = json.loads(row[0])
        if result.get("schema") not in {1, 2}:
            raise ValueError("Unsupported index version: rebuild with setup")
        return result

    @staticmethod
    def status(meta: dict) -> dict:
        changed = []
        for before in meta["assemblies"] + meta["source_files"] + meta.get("practice_files", []):
            try:
                if stamp(Path(before["path"])) != before:
                    changed.append(before["path"])
            except OSError:
                changed.append(before["path"])
        # New C# files also invalidate an explicitly indexed source directory.
        expected = {entry["path"] for entry in meta["source_files"]}
        for root in meta.get("source_roots", []):
            directory = Path(root)
            if not directory.is_dir():
                changed.append(root)
                continue
            for path in directory.rglob("*.cs"):
                relative = path.relative_to(directory)
                if any(p in {".git", ".venv", "obj", "bin", "node_modules"} for p in relative.parts):
                    continue
                resolved = path.resolve()
                if resolved.is_relative_to(directory.resolve()) and str(resolved) not in expected:
                    changed.append(str(resolved))
        rebuild = meta.get("schema", 1) < 2 or meta.get("builder_version") != __version__
        return {
            "stale": bool(changed) or rebuild, "changed": changed[:20],
            "index_upgrade_needed": rebuild,
            "has_installed_game_evidence": bool(meta["assemblies"]),
            "built_utc": meta["built_utc"], "official_commit": meta["official_commit"],
            "official_freshness": "Pinned at setup; not checked online during tool calls",
        }

    def response(self, db, **values):
        return {"snapshot": self.status(self.metadata(db)), **values}

    def doctor(self):
        with self.open() as db:
            meta = self.metadata(db)
            return self.response(
                db, version=__version__, counts=meta["counts"],
                assemblies=meta["assemblies"], parser_errors=meta["parse_errors"],
                parser_issues=self.parse_issues(db),
                official_repository="https://github.com/" + meta["official_repo"],
                limitations=meta["limitations"], workflow=WORKFLOW,
                next_step="Search official docs, then search_symbols. Re-run setup after a game update.",
            )

    @staticmethod
    def bounds(query: str, limit: int, offset: int):
        if not query.strip() or len(query) > 160:
            raise ValueError("query must contain 1-160 characters")
        if not 1 <= limit <= 50 or not 0 <= offset <= 100_000:
            raise ValueError("limit must be 1-50; offset must be 0-100000")

    def symbols(self, query: str, limit: int = 10, offset: int = 0):
        self.bounds(query, limit, offset)
        with self.open() as db:
            rows = db.execute("""
                SELECT s.id AS symbol_id,s.name,s.qualified,s.kind,s.signature,
                  s.start,s.end,s.file_id,f.corpus,f.path,f.origin
                FROM symbols s JOIN files f ON f.id=s.file_id
                WHERE instr(lower(s.qualified),lower(?))>0
                ORDER BY (s.name=? COLLATE NOCASE) DESC, length(s.qualified),s.id
                LIMIT ? OFFSET ?
            """, (query, query, limit + 1, offset)).fetchall()
            return self.response(
                db, matches=[dict(r) for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
                next_step="Call read_symbol with a returned symbol_id. Overloads have different IDs.",
            )

    def search(self, query: str, corpus: str = "all", limit: int = 10, offset: int = 0):
        self.bounds(query, limit, offset)
        if corpus not in {"all", "game", "source", "official", "practice"}:
            raise ValueError("corpus must be all, game, source, official or practice")
        with self.open() as db:
            rows = db.execute("""
                SELECT l.file_id,l.line,l.text,f.path,f.corpus,f.origin
                FROM lines l JOIN files f ON f.id=l.file_id
                WHERE (?='all' OR f.corpus=?) AND instr(lower(l.text),lower(?))>0
                ORDER BY f.id,l.line LIMIT ? OFFSET ?
            """, (corpus, corpus, query, limit + 1, offset)).fetchall()
            matches = [dict(r) for r in rows[:limit]]
            for match in matches:
                match["text"] = match["text"][:1500]
            return self.response(db, matches=matches,
                                 next_offset=offset + limit if len(rows) > limit else None,
                                 next_step="Call read_lines(file_id, start_line) for surrounding context.")

    def _read(self, db, file_id: int, start_line: int, count: int):
        if file_id < 1 or start_line < 1 or not 1 <= count <= 120:
            raise ValueError("Use a discovered file_id; start_line >= 1; count 1-120")
        file = db.execute("SELECT id,corpus,path,origin FROM files WHERE id=?", (file_id,)).fetchone()
        if file is None:
            raise ValueError("Unknown file_id: search first")
        rows = db.execute(
            "SELECT line,text FROM lines WHERE file_id=? AND line>=? ORDER BY line LIMIT ?",
            (file_id, start_line, count + 1),
        ).fetchall()
        lines, used = [], 0
        for row in rows[:count]:
            text = row["text"]
            if len(text) > 6000:
                text = text[:6000] + " [line truncated]"
            if lines and used + len(text) > 24_000:
                break
            lines.append({"line": row["line"], "text": text})
            used += len(text)
        next_line = lines[-1]["line"] + 1 if lines and len(rows) > len(lines) else None
        return {"file": dict(file), "lines": lines, "next_line": next_line,
                "parser_issues": self.parse_issues(db, file_id)}

    def parse_issues(self, db, file_id: int | None = None):
        if self.metadata(db)["schema"] < 2:
            return {"available": False, "next_step": "Rebuild the old index for issue locations."}
        condition = "" if file_id is None else "WHERE p.file_id=?"
        params = () if file_id is None else (file_id,)
        rows = db.execute(
            "SELECT p.file_id,f.path,f.origin,p.start,p.end,p.kind,p.excerpt "
            "FROM parse_issues p JOIN files f ON f.id=p.file_id " + condition +
            " ORDER BY p.file_id,p.start LIMIT 21", params,
        ).fetchall()
        return {"available": True, "issues": [dict(row) for row in rows[:20]],
                "more": len(rows) > 20,
                "next_step": "Use read_lines at the reported location; text remains available."}

    def read(self, file_id: int, start_line: int = 1, count: int = 60):
        with self.open() as db:
            return self.response(db, **self._read(db, file_id, start_line, count))

    def symbol(self, symbol_id: int, count: int = 100):
        with self.open() as db:
            row = db.execute("SELECT * FROM symbols WHERE id=?", (symbol_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown symbol_id: call search_symbols first")
            result = self._read(db, row["file_id"], row["start"],
                                min(max(1, count), 120, row["end"] - row["start"] + 1))
            if result["lines"] and result["lines"][-1]["line"] >= row["end"]:
                result["next_line"] = None
            return self.response(db, symbol=dict(row), **result)

    def references(self, member: str, limit: int = 10, offset: int = 0):
        self.bounds(member, limit, offset)
        with self.open() as db:
            rows = db.execute("""
                SELECT r.file_id,r.line,r.name,r.expression,r.kind,
                  r.caller_id AS caller_symbol_id,s.qualified AS enclosing_symbol,
                  f.path,f.corpus,f.origin
                FROM refs r JOIN files f ON f.id=r.file_id
                LEFT JOIN symbols s ON s.id=r.caller_id
                WHERE r.name=? COLLATE NOCASE
                ORDER BY r.file_id,r.line LIMIT ? OFFSET ?
            """, (member, limit + 1, offset)).fetchall()
            return self.response(
                db, references=[dict(r) for r in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
                resolution="Syntax only: same-name members may have different target types. "
                           "Reflection, delegates and dynamic calls may be absent.",
                next_step="Read enclosing callers and validate receiver types before choosing a patch.",
            )

    def guide(self, topic: str):
        topic = topic.lower().strip()
        if topic not in TOPICS:
            return {"topics": list(TOPICS), "workflow": WORKFLOW,
                    "next_step": "Choose one topic exactly as listed."}
        terms, names = TOPICS[topic]
        result = {
            "topic": topic, "workflow": WORKFLOW,
            "official_search_terms": terms.split(),
            "symbol_search_terms": names,
            "note": "These are search suggestions, not proven available APIs. "
                    "Read actual results and official support rules before coding.",
            "rules": [
                "An empty result means not found, never permission to invent a method.",
                "Read overloads, guards, return semantics, ownership and save effects.",
                "Init/OnEnable is not a loaded-game callback; load hooks are not per-frame ticks.",
                "Prefer supported ModHelper/ModHook APIs and original UI.",
                "Do not patch loading, trust, scanner or Steam protection code.",
                "Never report a successful build as successful gameplay verification.",
            ],
        }
        if topic in {"ui", "scene", "inventory", "highlight"}:
            result["practice"] = {
                "origin": "ProbablySage community practice, not official API or a visual test pass",
                "path": "practice/native-ui.md",
                "content": (PRACTICE_ROOT / "native-ui.md").read_text(encoding="utf-8"),
            }
        if topic == "network":
            result["practice"] = {
                "origin": "ProbablySage community practice; card visibility confirmed, effect fix pending gameplay verification",
                "path": "practice/network-upgrades.md",
                "content": (PRACTICE_ROOT / "network-upgrades.md").read_text(encoding="utf-8"),
            }
        return result

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from probablysage.catalog import Catalog
from probablysage.index import build

FIXTURE = """namespace Example;
public class Cabinet {
    public int Stock;
    public int Accept(int count) { return count; }
    public bool Accept(string name) { return name.Length > 0; }
    public int Trade() { return Accept(Stock); }
    public T Lookup<T>() { return default(T); }
    public T Use<T>(Cabinet other) { other.Lookup<int>(); return Lookup<T>(); }
}
"""


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.file = self.source / "柜体.cs"
        self.file.write_text(FIXTURE, encoding="utf-8")
        self.data = self.root / "data"
        build(self.data, None, [self.source], skip_docs=True)
        self.catalog = Catalog(self.data)

    def tearDown(self):
        self.temporary.cleanup()

    def test_overloads_and_call_evidence(self):
        hits = self.catalog.symbols("Accept")["matches"]
        self.assertEqual(len(hits), 2)
        self.assertNotEqual(hits[0]["symbol_id"], hits[1]["symbol_id"])
        self.assertTrue(any("int count" in h["signature"] for h in hits))
        read = self.catalog.symbol(hits[0]["symbol_id"])
        self.assertEqual(read["file"]["path"], "柜体.cs")
        self.assertTrue(read["lines"])
        self.assertIsNone(read["next_line"])
        refs = self.catalog.references("Accept")["references"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["enclosing_symbol"], "Example.Cabinet.Trade")
        self.assertEqual(self.catalog.doctor()["parser_errors"], 0)

    def test_missing_and_bounds(self):
        self.assertEqual(self.catalog.symbols("MissingMethod")["matches"], [])
        with self.assertRaises(ValueError):
            self.catalog.read(-1)
        with self.assertRaises(ValueError):
            self.catalog.read(99999)
        with self.assertRaises(ValueError):
            self.catalog.search("Accept", limit=10000)
        self.assertEqual(self.catalog.search("' OR 1=1 --")["matches"], [])
        page = self.catalog.symbols("Accept", limit=1)
        self.assertEqual(page["next_offset"], 1)
        self.assertEqual(len(self.catalog.symbols("Accept", limit=1, offset=1)["matches"]), 1)

    def test_generic_calls_keep_short_names(self):
        refs = self.catalog.references("Lookup")["references"]
        self.assertEqual(len(refs), 2)
        self.assertTrue(all("<" in hit["expression"] for hit in refs))
        self.assertTrue(all(hit["enclosing_symbol"] == "Example.Cabinet.Use" for hit in refs))

    def test_parser_issues_keep_text_and_locations(self):
        broken = self.source / "Broken.cs"
        broken.write_text("class Broken {\n void Bad( { value. }\n", encoding="utf-8")
        build(self.data, None, [self.source], skip_docs=True)
        diagnostics = self.catalog.doctor()
        self.assertGreater(diagnostics["parser_errors"], 0)
        issue = diagnostics["parser_issues"]["issues"][0]
        self.assertEqual(issue["path"], "Broken.cs")
        self.assertGreaterEqual(issue["start"], 1)
        read = self.catalog.read(issue["file_id"])
        self.assertTrue(read["parser_issues"]["issues"])
        self.assertTrue(any("value." in line["text"] for line in read["lines"]))

    def test_practice_is_queryable_and_distinct_from_official(self):
        for topic, query in (("ui", "PixelWindow"), ("network", "RegisterModUpgrade")):
            with self.subTest(topic=topic):
                practice = self.catalog.guide(topic)["practice"]
                self.assertIn("不是官方", practice["content"])
                found = self.catalog.search(query, corpus="practice")["matches"]
                self.assertTrue(found)
                self.assertTrue(all(hit["corpus"] == "practice" for hit in found))
                self.assertEqual(self.catalog.search(query, corpus="official")["matches"], [])

    def test_old_index_is_readable_but_requests_rebuild(self):
        import sqlite3
        with sqlite3.connect(self.catalog.database) as db:
            meta = json.loads(db.execute("SELECT value FROM metadata").fetchone()[0])
            meta["schema"] = 1
            meta.pop("builder_version")
            db.execute("UPDATE metadata SET value=?", (json.dumps(meta),))
        self.assertTrue(self.catalog.doctor()["snapshot"]["index_upgrade_needed"])
        self.assertFalse(self.catalog.doctor()["parser_issues"]["available"])
        self.assertTrue(self.catalog.symbols("Accept")["matches"])

    def test_snapshot_staleness_and_immutability(self):
        self.assertFalse(self.catalog.doctor()["snapshot"]["stale"])
        self.file.write_text(FIXTURE + "// source changed\n", encoding="utf-8")
        self.assertTrue(self.catalog.doctor()["snapshot"]["stale"])
        self.assertEqual(self.catalog.search("source changed")["matches"], [])

    def test_new_file_and_failed_rebuild(self):
        (self.source / "New.cs").write_text("class New {}", encoding="utf-8")
        self.assertTrue(self.catalog.doctor()["snapshot"]["stale"])
        with patch("probablysage.index.fetch_json", side_effect=ValueError("offline")):
            with self.assertRaises(ValueError):
                build(self.data, None, [self.source])
        self.assertEqual(len(self.catalog.symbols("Accept")["matches"]), 2)

    def test_real_stdio_protocol(self):
        async def run():
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "probablysage", "--data", str(self.data), "serve"],
            )
            async with Client(parameters, read_timeout_seconds=15) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 8)
                doctor = await client.call_tool("doctor", {})
                self.assertFalse(doctor.is_error)
                result = await client.call_tool("search_symbols", {"query": "Accept"})
                self.assertFalse(result.is_error)
                # MCP clients can consume either structured content or JSON text.
                text = next(c.text for c in result.content if c.type == "text")
                payload = json.loads(text)
                self.assertEqual(len(payload["matches"]), 2)
                read = await client.call_tool("read_symbol", {
                    "symbol_id": payload["matches"][0]["symbol_id"],
                })
                self.assertFalse(read.is_error)
                guide = await client.call_tool("development_guide", {"topic": "ui"})
                self.assertFalse(guide.is_error)
                guide_text = next(c.text for c in guide.content if c.type == "text")
                self.assertIn("practice", json.loads(guide_text))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

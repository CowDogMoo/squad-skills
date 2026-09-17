#!/usr/bin/env python3
"""Fetch, cache, and query the official Ableton Live manual.

Zero dependencies (Python 3.9+ standard library only). The manual is pulled
from https://www.ableton.com/en/live-manual/<version>/ once, parsed into
numbered sections, and cached as JSON so every later query is offline and
instant.

Commands:

    live_manual.py sync [--force]             download every chapter into the cache
    live_manual.py toc [chapter]              chapters, or the sections of one chapter
    live_manual.py search QUERY [-n N] [--chapter SLUG] [--json]
    live_manual.py show 6.13 | show consolidating-clips | show "Consolidating Clips"
    live_manual.py shortcuts [FILTER] [--windows]
    live_manual.py status                     where the cache is and how old it is

Cache location: $LIVE_MANUAL_CACHE, else ~/.cache/ableton-live-manual/<version>/.
Every query auto-syncs when the cache is missing; pass --offline to forbid
network access (missing cache then exits 3).

Exit codes: 0 ok, 1 no results, 2 usage error, 3 network/cache failure.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_VERSION = "12"
BASE = "https://www.ableton.com/en/live-manual/{version}/"
USER_AGENT = "Mozilla/5.0 (live_manual.py; squad-skills ableton-live-computer-use)"
TIMEOUT = 30

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "the", "this", "to", "with", "you",
    "your", "do", "does", "can", "what", "where", "when",
}


# ---------------------------------------------------------------- cache paths
def cache_dir(version: str) -> Path:
    env = os.environ.get("LIVE_MANUAL_CACHE")
    root = Path(env).expanduser() if env else Path.home() / ".cache" / "ableton-live-manual"
    return root / version


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- HTML parsing
class MainExtractor(HTMLParser):
    """Collect the raw HTML between <main> and </main>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.depth += 1
            return
        if self.depth:
            self.parts.append(self.get_starttag_text() or "")

    def handle_startendtag(self, tag, attrs):
        if self.depth:
            self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag):
        if tag == "main" and self.depth:
            self.depth -= 1
            return
        if self.depth:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.depth:
            self.parts.append(f"&#{name};")


class SectionParser(HTMLParser):
    """Turn the <main> HTML of a chapter into numbered sections of plain text.

    Headings h1-h4 carrying data-number start a new section. Paragraphs, list
    items, table rows, and figure captions become lines. <kbd> runs become
    "Cmd+Shift+W" style tokens so shortcut tables survive as text.
    """

    BLOCK_END = {"p", "li", "figcaption", "tr", "h1", "h2", "h3", "h4", "h5", "dt", "dd"}
    FIGCAPTION = "figcaption"

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[dict] = []
        self.current: dict | None = None
        self.buf: list[str] = []
        self.in_heading: str | None = None
        self.heading_attrs: dict = {}
        self.list_stack: list[str] = []
        self.cell_buf: list[str] = []
        self.row_cells: list[str] = []
        self.in_cell = False
        self.in_table = False
        self.prev_kbd = False
        self.skip_depth = 0
        self.table_rows: list[list[str]] = []

    # -- helpers
    def _flush_line(self) -> None:
        text = re.sub(r"[ \t\r\n]+", " ", "".join(self.buf)).strip()
        self.buf = []
        if text and self.current is not None:
            prefix = ""
            if self.list_stack:
                prefix = "- " if self.list_stack[-1] == "ul" else "1. "
            self.current["lines"].append(prefix + text)

    def _start_section(self, level: int, number: str, sid: str, title: str) -> None:
        self.current = {
            "level": level,
            "number": number,
            "id": sid,
            "title": title,
            "lines": [],
            "shortcuts": [],
        }
        self.sections.append(self.current)

    # -- parser callbacks
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in ("aside", "form", "noscript", "script", "style", "nav", "button"):
            self.skip_depth = 1
            return
        if tag in ("h1", "h2", "h3", "h4") and (a.get("data-number") or a.get("id")):
            self._flush_line()
            self.in_heading = tag
            self.heading_attrs = a
            self.buf = []
            return
        if tag in ("ul", "ol"):
            self._flush_line()
            self.list_stack.append(tag)
        elif tag == "li":
            self._flush_line()
        elif tag == "table":
            self._flush_line()
            self.in_table = True
            self.table_rows = []
        elif tag == "tr":
            self.row_cells = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self.cell_buf = []
            self.prev_kbd = False
        elif tag == "kbd":
            if self.prev_kbd:
                (self.cell_buf if self.in_cell else self.buf).append("+")
        elif tag == "br":
            (self.cell_buf if self.in_cell else self.buf).append(" ")
        elif tag == "figcaption":
            self._flush_line()
            self.buf.append("[Figure: ")
        elif tag == "img":
            alt = (a.get("alt") or "").strip()
            if alt:
                self.buf.append(f"[image: {alt}]")

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == self.in_heading:
            raw = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            number = self.heading_attrs.get("data-number", "")
            title = raw
            if number and raw.startswith(number):
                title = raw[len(number):].strip().lstrip(".").strip()
            level = int(tag[1])
            self._start_section(level, number, self.heading_attrs.get("id", ""), title)
            self.in_heading = None
            self.buf = []
            return
        if tag in ("td", "th"):
            cell = re.sub(r"\s+", " ", "".join(self.cell_buf)).strip()
            self.row_cells.append(cell)
            self.in_cell = False
            self.prev_kbd = False
        elif tag == "tr":
            if any(self.row_cells):
                self.table_rows.append(self.row_cells)
            self.row_cells = []
        elif tag == "table":
            self.in_table = False
            self._emit_table()
        elif tag in ("ul", "ol"):
            self._flush_line()
            if self.list_stack:
                self.list_stack.pop()
        elif tag == "figcaption":
            self.buf.append("]")
            self._flush_line()
        elif tag in self.BLOCK_END:
            self._flush_line()
        elif tag == "kbd":
            self.prev_kbd = True
            return
        if tag != "kbd":
            self.prev_kbd = False

    def handle_data(self, data):
        if self.skip_depth:
            return
        if data.strip():
            self.prev_kbd = self.prev_kbd and not data.strip()
        if self.in_cell:
            self.cell_buf.append(data)
        else:
            self.buf.append(data)

    def _emit_table(self) -> None:
        if self.current is None or not self.table_rows:
            return
        header = self.table_rows[0]
        is_shortcut_table = len(header) >= 3 and header[1].lower() == "windows" and header[2].lower() == "mac"
        body = self.table_rows[1:] if is_shortcut_table or not header[0] else self.table_rows
        for row in body:
            if is_shortcut_table and len(row) >= 3 and row[0]:
                self.current["shortcuts"].append({"action": row[0], "windows": row[1], "mac": row[2]})
                self.current["lines"].append(f"{row[0]}: Mac {row[2]} | Windows {row[1]}")
            else:
                self.current["lines"].append(" | ".join(c for c in row if c))

    def close(self):
        self._flush_line()
        super().close()


def parse_chapter(page_html: str, slug: str, url: str) -> dict:
    ext = MainExtractor()
    ext.feed(page_html)
    ext.close()
    main_html = "".join(ext.parts)
    sp = SectionParser()
    sp.feed(main_html)
    sp.close()
    sections = [s for s in sp.sections if s["number"] or s["lines"]]
    for s in sections:
        s["text"] = "\n".join(s["lines"])
        s["url"] = f"{url}#{s['id']}" if s["id"] else url
        del s["lines"]
    h1 = next((s for s in sections if s["level"] == 1), None)
    return {
        "slug": slug,
        "url": url,
        "number": h1["number"].rstrip(".") if h1 else "",
        "title": h1["title"] if h1 else slug.replace("-", " ").title(),
        "sections": sections,
    }


def parse_index(index_html: str, version: str) -> list[str]:
    prefix = f"/en/live-manual/{version}/"
    slugs: list[str] = []
    for m in re.finditer(r'href="' + re.escape(prefix) + r'([a-z0-9-]+)/', index_html):
        slug = m.group(1)
        if slug not in slugs:
            slugs.append(slug)
    return slugs


# ---------------------------------------------------------------- sync
def sync(version: str, force: bool = False, quiet: bool = False, reparse: bool = False) -> Path:
    cdir = cache_dir(version)
    (cdir / "raw").mkdir(parents=True, exist_ok=True)
    (cdir / "chapters").mkdir(parents=True, exist_ok=True)
    base = BASE.format(version=version)
    try:
        index_html = fetch(base)
    except (urllib.error.URLError, OSError) as exc:
        print(f"error: could not fetch manual index {base}: {exc}", file=sys.stderr)
        sys.exit(3)
    slugs = parse_index(index_html, version)
    if not slugs:
        print("error: manual index had no chapter links; site layout may have changed", file=sys.stderr)
        sys.exit(3)
    chapters = []
    for i, slug in enumerate(slugs, 1):
        raw_path = cdir / "raw" / f"{slug}.html"
        json_path = cdir / "chapters" / f"{slug}.json"
        url = f"{base}{slug}/"
        if json_path.exists() and raw_path.exists() and not force and not reparse:
            chapters.append(json.loads(json_path.read_text(encoding="utf-8")))
            continue
        if raw_path.exists() and not force:
            page = raw_path.read_text(encoding="utf-8")
        else:
            if not quiet:
                print(f"[{i:2d}/{len(slugs)}] {slug}", file=sys.stderr)
            try:
                page = fetch(url)
            except (urllib.error.URLError, OSError) as exc:
                print(f"error: could not fetch {url}: {exc}", file=sys.stderr)
                sys.exit(3)
            raw_path.write_text(page, encoding="utf-8")
            time.sleep(0.2)
        chapter = parse_chapter(page, slug, url)
        json_path.write_text(json.dumps(chapter, ensure_ascii=False, indent=1), encoding="utf-8")
        chapters.append(chapter)

    def chapter_key(c: dict):
        try:
            return (0, int(c["number"]))
        except ValueError:
            return (1, c["slug"])

    chapters.sort(key=chapter_key)
    index = {
        "version": version,
        "base": base,
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "chapters": [
            {"slug": c["slug"], "number": c["number"], "title": c["title"], "url": c["url"], "sections": len(c["sections"])}
            for c in chapters
        ],
    }
    (cdir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    if not quiet:
        print(f"synced {len(chapters)} chapters into {cdir}", file=sys.stderr)
    return cdir


def load(version: str, offline: bool) -> tuple[dict, list[dict]]:
    cdir = cache_dir(version)
    index_path = cdir / "index.json"
    if not index_path.exists():
        if offline:
            print(f"error: no cache at {cdir} and --offline was given; run `live_manual.py sync`", file=sys.stderr)
            sys.exit(3)
        sync(version)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    chapters = []
    for entry in index["chapters"]:
        p = cdir / "chapters" / f"{entry['slug']}.json"
        if p.exists():
            chapters.append(json.loads(p.read_text(encoding="utf-8")))
    return index, chapters


# ---------------------------------------------------------------- queries
def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9+/.-]*", text.lower())]


def find_chapter(chapters: list[dict], key: str) -> dict | None:
    key_l = key.lower().strip()
    for c in chapters:
        if c["slug"] == key_l or c["number"] == key_l or c["title"].lower() == key_l:
            return c
    for c in chapters:
        if key_l in c["slug"] or key_l in c["title"].lower():
            return c
    return None


def cmd_toc(args, chapters):
    if args.chapter:
        c = find_chapter(chapters, args.chapter)
        if not c:
            print(f"no chapter matches {args.chapter!r}", file=sys.stderr)
            return 1
        for s in c["sections"]:
            indent = "  " * (s["level"] - 1)
            print(f"{indent}{s['number']:<8} {s['title']}    [{s['id']}]")
        return 0
    if args.json:
        print(json.dumps([{k: c[k] for k in ("number", "slug", "title", "url")} | {"sections": len(c["sections"])} for c in chapters], indent=1))
        return 0
    for c in chapters:
        print(f"{c['number']:>3}  {c['title']:<52} {c['slug']}  ({len(c['sections'])} sections)")
    return 0


def score_section(terms: list[str], section: dict) -> tuple[float, int]:
    text_l = section["text"].lower()
    title_l = section["title"].lower()
    words = tokenize(text_l)
    if not words and not title_l:
        return 0.0, 0
    hits = 0
    score = 0.0
    for t in terms:
        n = text_l.count(t)
        in_title = t in title_l
        if n or in_title:
            hits += 1
        score += min(n, 20) * 1.0 + (8.0 if in_title else 0.0)
    if hits:
        score *= hits / len(terms)
        score /= 1 + (len(words) / 800.0)
    return score, hits


def snippet(text: str, terms: list[str], width: int = 220) -> str:
    low = text.lower()
    pos = -1
    for t in terms:
        p = low.find(t)
        if p != -1 and (pos == -1 or p < pos):
            pos = p
    if pos == -1:
        return text[:width].replace("\n", " ")
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    s = text[start:end].replace("\n", " ")
    return ("…" if start else "") + s + ("…" if end < len(text) else "")


def cmd_search(args, chapters):
    terms = [t for t in tokenize(args.query) if t not in STOPWORDS] or tokenize(args.query)
    if not terms:
        print("usage: give at least one search term", file=sys.stderr)
        return 2
    pool = chapters
    if args.chapter:
        c = find_chapter(chapters, args.chapter)
        if not c:
            print(f"no chapter matches {args.chapter!r}", file=sys.stderr)
            return 1
        pool = [c]
    results = []
    for c in pool:
        for s in c["sections"]:
            sc, hits = score_section(terms, s)
            if hits:
                results.append((sc, hits, c, s))
    if not results:
        print(f"no results for {args.query!r} (terms: {' '.join(terms)})", file=sys.stderr)
        return 1
    full = [r for r in results if r[1] == len(terms)]
    results = full if full else results
    results.sort(key=lambda r: -r[0])
    results = results[: args.limit]
    if args.json:
        print(json.dumps([
            {"chapter": c["title"], "chapter_number": c["number"], "slug": c["slug"], "section": s["number"],
             "title": s["title"], "id": s["id"], "url": s["url"], "score": round(sc, 2), "snippet": snippet(s["text"], terms)}
            for sc, hits, c, s in results], indent=1, ensure_ascii=False))
        return 0
    if not full:
        print(f"(no section contains every term; showing partial matches for: {' '.join(terms)})")
    for sc, hits, c, s in results:
        num = s["number"] or c["number"]
        print(f"{num:<8} {s['title']}  —  {c['title']}")
        print(f"         {s['url']}")
        print(f"         {snippet(s['text'], terms)}")
        print()
    return 0


def resolve_section(chapters: list[dict], key: str) -> list[tuple[dict, dict]]:
    key_s = key.strip()
    key_l = key_s.lower()
    out = []
    for c in chapters:
        for s in c["sections"]:
            if s["number"].rstrip(".") == key_s.rstrip(".") or s["id"] == key_l or s["title"].lower() == key_l:
                out.append((c, s))
    if out:
        return out
    for c in chapters:
        if c["slug"] == key_l or c["number"] == key_s:
            return [(c, s) for s in c["sections"] if s["level"] == 1]
    for c in chapters:
        for s in c["sections"]:
            if key_l in s["title"].lower() or key_l in s["id"]:
                out.append((c, s))
    return out


def cmd_show(args, chapters):
    matches = resolve_section(chapters, args.section)
    if not matches:
        print(f"no section matches {args.section!r}; try `toc` or `search`", file=sys.stderr)
        return 1
    if len(matches) > 1 and not args.all:
        print(f"{len(matches)} sections match {args.section!r}; pick one by number, or pass --all:")
        for c, s in matches:
            print(f"  {s['number']:<8} {s['title']}  —  {c['title']}  [{s['id']}]")
        return 0
    for c, s in matches:
        chapter_sections = c["sections"]
        idx = chapter_sections.index(s)
        block = [s]
        if args.deep:
            for nxt in chapter_sections[idx + 1:]:
                if nxt["level"] <= s["level"]:
                    break
                block.append(nxt)
        for b in block:
            hashes = "#" * b["level"]
            print(f"{hashes} {b['number']} {b['title']}".rstrip())
            print(f"<{b['url']}>")
            print()
            print(b["text"])
            print()
    return 0


def cmd_shortcuts(args, chapters):
    flt = (args.filter or "").lower()
    col = "windows" if args.windows else "mac"
    rows = []
    for c in chapters:
        for s in c["sections"]:
            for sc in s.get("shortcuts", []):
                if not flt or flt in sc["action"].lower() or flt in sc[col].lower() or flt in s["title"].lower():
                    rows.append((s["title"], sc["action"], sc[col]))
    if not rows:
        print(f"no shortcuts match {args.filter!r}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([{"section": a, "action": b, col: k} for a, b, k in rows], indent=1, ensure_ascii=False))
        return 0
    last = None
    for section, action, keys in rows:
        if section != last:
            print(f"\n## {section}")
            last = section
        print(f"  {action:<60} {keys}")
    return 0


def cmd_status(args, version):
    cdir = cache_dir(version)
    index_path = cdir / "index.json"
    if not index_path.exists():
        print(f"cache: {cdir} (empty; run sync)")
        return 1
    index = json.loads(index_path.read_text(encoding="utf-8"))
    print(f"cache: {cdir}")
    print(f"version: {index['version']}  synced_at: {index['synced_at']}  chapters: {len(index['chapters'])}")
    return 0


# ---------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default=DEFAULT_VERSION, help="manual major version (default 12)")
    ap.add_argument("--offline", action="store_true", help="never touch the network")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sync", help="download and parse every chapter")
    p.add_argument("--force", action="store_true", help="re-download even if cached")
    p.add_argument("--reparse", action="store_true", help="re-parse the cached HTML without downloading")

    p = sub.add_parser("toc", help="list chapters, or one chapter's sections")
    p.add_argument("chapter", nargs="?")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="full-text search across sections")
    p.add_argument("query")
    p.add_argument("-n", "--limit", type=int, default=8)
    p.add_argument("--chapter", help="restrict to one chapter (slug, number, or title)")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("show", help="print a section by number, id, or title")
    p.add_argument("section")
    p.add_argument("--deep", action="store_true", help="include subsections")
    p.add_argument("--all", action="store_true", help="print every match instead of listing them")

    p = sub.add_parser("shortcuts", help="list keyboard shortcuts (Mac by default)")
    p.add_argument("filter", nargs="?")
    p.add_argument("--windows", action="store_true")
    p.add_argument("--json", action="store_true")

    sub.add_parser("status", help="report cache location and age")

    args = ap.parse_args(argv)
    if args.cmd == "sync":
        sync(args.version, force=args.force, reparse=args.reparse)
        return 0
    if args.cmd == "status":
        return cmd_status(args, args.version)
    _, chapters = load(args.version, args.offline)
    if args.cmd == "toc":
        return cmd_toc(args, chapters)
    if args.cmd == "search":
        return cmd_search(args, chapters)
    if args.cmd == "show":
        return cmd_show(args, chapters)
    if args.cmd == "shortcuts":
        return cmd_shortcuts(args, chapters)
    return 2


if __name__ == "__main__":
    sys.exit(main())

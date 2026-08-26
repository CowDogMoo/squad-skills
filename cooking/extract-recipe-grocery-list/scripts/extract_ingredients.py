#!/usr/bin/env python3
"""Extract recipe ingredients from recipe pages.

Usage:
    extract_ingredients.py URL [URL ...]          # fetch and extract each
    extract_ingredients.py --stdin < page.html    # extract from HTML on stdin
    extract_ingredients.py --json URL ...         # machine-readable output

Prefers schema.org JSON-LD (`recipeIngredient`), walking `@graph` and nested
arrays so wrapped recipes are found; falls back to scraping the visible
ingredients list. HTML entities are decoded because JSON-LD on many recipe
sites carries encoded text (`&#8217;`). Only the standard library is used so
the script runs on any host with python3.

Exit status is 0 even when a URL fails; failures are reported per URL so one
bad recipe never aborts a shopping list.
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; squad-skills extract-recipe-grocery-list)"
LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


def _walk(node):
    """Yield every dict reachable from a JSON-LD node (handles @graph / lists)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def from_jsonld(page):
    for block in LD_RE.findall(page):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            # Some sites emit trailing commas or comments; a loose regex still
            # gets the array in most of those cases.
            m = re.search(r'"recipeIngredient"\s*:\s*(\[.*?\])', block, re.S)
            if m:
                try:
                    return [html.unescape(x) for x in json.loads(m.group(1))]
                except json.JSONDecodeError:
                    pass
            continue
        for node in _walk(data):
            ing = node.get("recipeIngredient")
            if isinstance(ing, list) and ing:
                return [html.unescape(str(x)).strip() for x in ing]
    return []


def from_visible(page):
    """Best-effort: <li> items inside an element whose class/id mentions ingredient."""
    m = re.search(
        r'<(ul|ol|div)[^>]*(?:class|id)=["\'][^"\']*ingredient[^"\']*["\'][^>]*>(.*?)</\1>',
        page, re.S | re.I,
    )
    if not m:
        return []
    items = re.findall(r"<li[^>]*>(.*?)</li>", m.group(2), re.S | re.I)
    out = []
    for it in items:
        text = html.unescape(re.sub(r"<[^>]+>", " ", it))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out


def extract(page):
    ing = from_jsonld(page)
    if ing:
        return ing, "json-ld"
    ing = from_visible(page)
    return ing, ("visible" if ing else "none")


def main(argv):
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    results = []
    if "--stdin" in argv:
        ing, source = extract(sys.stdin.read())
        results.append({"url": "<stdin>", "source": source, "ingredients": ing})
    else:
        for url in argv:
            try:
                ing, source = extract(fetch(url))
                results.append({"url": url, "source": source, "ingredients": ing})
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                results.append({"url": url, "source": "error", "error": str(exc), "ingredients": []})
    if as_json:
        json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return
    for r in results:
        print(f"== {r['url']}  [{r['source']}]" + (f"  {r['error']}" if "error" in r else ""))
        for line in r["ingredients"]:
            print(line)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1:])

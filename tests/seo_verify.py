#!/usr/bin/env python3
"""
SEO quick-wins + Hindi pages — verification suite for a buildless static site.

Every assertion here corresponds to a specific invariant in the plan's
IMPLICIT_SPEC.md or a success criterion in PLAN.md. The suite reads the
static files from disk (no server needed for the file-content checks) and
makes real, meaningful assertions — it exits non-zero on the first failure.

Run:   python3 tests/seo_verify.py
       python3 tests/seo_verify.py --root /path/to/site   (default: repo root)

This is the test harness for this repo. There is no build step and no
framework dependency (stdlib only) so it runs anywhere Python 3 does.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# --------------------------------------------------------------------------- #
# Tiny test framework (stdlib only) — counts pass/fail, exits non-zero on fail.
# --------------------------------------------------------------------------- #

class Suite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.current = ""

    def section(self, name):
        self.current = name

    def check(self, cond, label, detail=""):
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            print(f"  FAIL: {label}" + (f" — {detail}" if detail else ""),
                  file=sys.stderr)
        return bool(cond)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"seo_verify: {self.passed}/{total} checks passed")
        if self.failed:
            print(f"{self.failed} FAILED — see messages above", file=sys.stderr)
        return 0 if self.failed == 0 else 1


S = Suite()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S
)
ALT_LINK_RE = re.compile(
    r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"'
)

def read(path):
    return Path(path).read_text(encoding="utf-8")

def ldjson_blocks(text):
    """Return list of parsed JSON objects from all ld+json blocks in text."""
    out = []
    for m in LDJSON_RE.finditer(text):
        out.append(json.loads(m.group(1)))
    return out

def all_nodes(obj):
    """Flatten a JSON-LD node, @graph array, or top-level list into a list of dicts."""
    if isinstance(obj, list):
        nodes = []
        for x in obj:
            nodes.extend(all_nodes(x))
        return nodes
    if isinstance(obj, dict):
        if "@graph" in obj and isinstance(obj["@graph"], list):
            nodes = []
            for x in obj["@graph"]:
                nodes.extend(all_nodes(x))
            # the wrapper itself is usually just {context, graph}; also keep it
            return nodes + [obj]
        return [obj]
    return []

def body_text(html):
    """Visible text of the body with scripts/styles/inline-tags stripped.

    FAQ answers in JSON-LD are plain text, but the matching visible body text
    may carry inline markup (e.g. an <a href="tel:..."> around a phone number,
    <strong>, etc.). To check JSON-LD text == visible text (inv. 8) we compare
    against the tag-stripped text content, not the raw HTML substring.
    Whitespace is collapsed so wrapping/newlines don't cause false negatives.
    """
    no_scripts = re.sub(r'<script[\s\S]*?</script>', '', html)
    no_styles = re.sub(r'<style[\s\S]*?</style>', '', no_scripts)
    no_head = re.sub(r'<head[\s\S]*?</head>', '', no_styles, flags=re.I)
    # strip all remaining tags but keep their inner text
    no_tags = re.sub(r'<[^>]+>', '', no_head)
    # collapse whitespace
    return re.sub(r'\s+', ' ', no_tags).strip()


def run(root: Path):
    root_str = str(root)
    pages = {
        "index":          root / "index.html",
        "treatments":     root / "treatments.html",
        "experience":     root / "experience.html",
        "credentials":    root / "credentials.html",
        "privacy":        root / "privacy.html",
        "404":            root / "404.html",
        "hi_index":       root / "hi" / "index.html",
        "hi_treatments":  root / "hi" / "treatments.html",
    }
    texts = {k: read(v) for k, v in pages.items()}

    # =================== Phase 1: delivery & caching =================== #
    S.section("Phase 1: delivery & caching")

    # _headers blocks exist for /, /*.avif, /i18n.js
    headers = read(root / "_headers")
    S.section("Phase 1 / _headers blocks")
    S.check(re.search(r'^/\s*$', headers, re.M) is not None,
            "_headers has explicit / block")
    S.check(re.search(r'^/\*\.(avif|webp)\s*$', headers, re.M) is not None
            or re.search(r'^/\*\.avif\s*$', headers, re.M) is not None,
            "_headers has /*.avif block")
    S.check(re.search(r'^/i18n\.js\s*$', headers, re.M) is not None,
            "_headers has /i18n.js block")

    # Hero preload switched to AVIF
    S.section("Phase 1 / hero preload AVIF")
    preload_line = re.search(r'<link rel="preload"[^>]*>', texts["index"])
    S.check(preload_line is not None
            and 'type="image/avif"' in preload_line.group(0)
            and '.avif' in preload_line.group(0),
            "index hero preload uses image/avif",
            preload_line.group(0) if preload_line else "no preload found")

    # Script deferral: 4 defers on the 5 page files; 404 unchanged at 1
    S.section("Phase 1 / script deferral")
    for name in ("index", "treatments", "experience", "credentials", "privacy"):
        n = len(re.findall(r'\bdefer\b', texts[name]))
        S.check(n == 4, f"{name}.html has exactly 4 defer attrs", f"got {n}")
    n404 = len(re.findall(r'\bdefer\b', texts["404"]))
    S.check(n404 == 1, "404.html defer count unchanged at 1", f"got {n404}")

    # sitemap: valid XML, no legacy JPG / %20, lastmod updated
    S.section("Phase 1 / sitemap")
    sitemap_path = root / "sitemap.xml"
    try:
        ET.parse(sitemap_path)
        sm_ok = True
    except ET.ParseError as e:
        sm_ok = False
        sm_err = str(e)
    S.check(sm_ok, "sitemap.xml parses as valid XML",
            "" if sm_ok else sm_err)
    sm = read(sitemap_path)
    legacy = len(re.findall(r'%20|\.jpg', sm))
    S.check(legacy == 0, "sitemap has no legacy-JPG or %20 refs", f"got {legacy}")
    S.check('2026-07-20' in sm, "sitemap lastmod updated to 2026-07-20")

    # =================== Phase 2: social-card parity =================== #
    S.section("Phase 2: social-card parity")
    for name in ("index", "treatments", "experience", "credentials", "privacy"):
        S.check('og-front-1200.webp' in texts[name],
                f"{name}.html uses og-front-1200.webp")
    S.check('og-front-1200.webp' not in texts["404"],
            "404.html has no og card (noindex, excluded)")
    for name in ("index", "treatments", "experience", "credentials", "privacy"):
        meta = re.search(
            r'<meta property="og:image" content="([^"]+)"[^>]*>'
            r'\s*<meta property="og:image:width" content="(\d+)">'
            r'\s*<meta property="og:image:height" content="(\d+)">',
            texts[name])
        S.check(meta is not None
                and meta.group(1).endswith('og-front-1200.webp')
                and meta.group(2) == '1200'
                and meta.group(3) == '630',
                f"{name}.html og:image is 1200x630 og-front-1200.webp")
    # privacy twitter card now summary_large_image with twitter:image
    S.check('twitter:card" content="summary_large_image"' in texts["privacy"],
            "privacy twitter:card is summary_large_image")
    S.check('twitter:image' in texts["privacy"],
            "privacy has twitter:image")

    # =================== Phase 3: structured-data hygiene =================== #
    S.section("Phase 3: structured data")
    # Every ld+json block on every page parses
    total_blocks = 0
    parse_failures = []
    for name, t in texts.items():
        for i, m in enumerate(LDJSON_RE.finditer(t)):
            total_blocks += 1
            try:
                json.loads(m.group(1))
            except json.JSONDecodeError as e:
                parse_failures.append(f"{name} block {i}: {e}")
    S.check(not parse_failures,
            f"all {total_blocks} ld+json blocks parse",
            "; ".join(parse_failures))
    # #physician @id present on experience/credentials/treatments
    for name in ("experience", "credentials", "treatments"):
        S.check('"@id": "https://uro-care.com/#physician"' in texts[name],
                f"{name}.html references canonical #physician @id")
    # experience/credentials mainEntity is Physician (not Person)
    for name in ("experience", "credentials"):
        m = re.search(r'"mainEntity":\s*\{[^}]*?"@type":\s*"(\w+)"', texts[name])
        S.check(m is not None and m.group(1) == "Physician",
                f"{name}.html mainEntity @type is Physician",
                m.group(1) if m else "no mainEntity found")
    # SearchAction gone from index
    S.check('SearchAction' not in texts["index"],
            "index.html has no SearchAction")
    # medicalSpecialty trimmed to clean enum on index Physician node
    ms = re.search(r'"medicalSpecialty":\s*(\[[^\]]*\]|"[^"]*")',
                   texts["index"])
    S.check(ms is not None and 'Urologic' in ms.group(1)
            and 'Robotic Surgery' not in ms.group(1),
            "index medicalSpecialty is clean Urologic enum",
            ms.group(1) if ms else "none")
    # treatments dateModified == visible "Last reviewed" month (inv. 8)
    dm = re.search(r'"dateModified":\s*"([^"]+)"', texts["treatments"])
    lr = re.search(r'Last reviewed:\s*(\w+) (\d{4})', texts["treatments"])
    S.check(dm is not None and dm.group(1) == "2026-07-20",
            "treatments dateModified is 2026-07-20",
            dm.group(1) if dm else "none")
    S.check(lr is not None and lr.group(1) == "July" and lr.group(2) == "2026",
            "treatments visible 'Last reviewed' is July 2026",
            f"{lr.group(1)} {lr.group(2)}" if lr else "none")

    # =================== Phase 4: Hindi pages + hreflang =================== #
    S.section("Phase 4: Hindi /hi/ pages")
    for name in ("hi_index", "hi_treatments"):
        t = texts[name]
        S.check('<html lang="hi-IN" class="lang-hi">' in t,
                f"{name} has static <html lang=hi-IN class=lang-hi>")
        S.check('i18n.js' not in t, f"{name} does NOT load i18n.js")
        S.check('data-i18n' not in t, f"{name} has no data-i18n attrs")
        S.check("localStorage.setItem('uro-lang','en')" in t,
                f"{name} English link sets uro-lang=en")
        S.check('name="robots" content="index, follow"' in t,
                f"{name} is index,follow")
        S.check('og:locale" content="hi_IN"' in t,
                f"{name} og:locale is hi_IN")
        S.check('SearchAction' not in t, f"{name} has no SearchAction")

    # Canonical/og:url/sitemap-loc triple agreement (inv. 1) for new pages
    S.section("Phase 4 / URL-shape consistency (inv. 1)")
    for name, canon in (("hi_index", "https://uro-care.com/hi/"),
                        ("hi_treatments", "https://uro-care.com/hi/treatments.html")):
        t = texts[name]
        c = re.search(r'<link rel="canonical" href="([^"]+)"', t)
        o = re.search(r'<meta property="og:url" content="([^"]+)"', t)
        S.check(c is not None and c.group(1) == canon,
                f"{name} canonical == {canon}", c.group(1) if c else "none")
        S.check(o is not None and o.group(1) == canon,
                f"{name} og:url == {canon}", o.group(1) if o else "none")
        S.check(f"<loc>{canon}</loc>" in sm,
                f"{name} appears in sitemap at {canon}")
    # Canonical on all INDEXABLE pages points to uro-care.com (inv. 11).
    # 404.html is noindex and carries no canonical (a canonical on a noindex
    # page is moot and the plan never touched 404's head); exclude it here.
    for name, t in texts.items():
        if name == "404":
            continue
        c = re.search(r'<link rel="canonical" href="([^"]+)"', t)
        S.check(c is not None and c.group(1).startswith("https://uro-care.com/"),
                f"{name} canonical points to uro-care.com",
                c.group(1) if c else "none")

    # Hreflang reciprocity (inv. 4): identical sets per cluster across the 4
    # page-tag sides AND the sitemap xhtml:link sides.
    S.section("Phase 4 / hreflang reciprocity (inv. 4)")
    def page_alt_set(path):
        return set(ALT_LINK_RE.findall(read(path)))
    def sm_alt_set(loc):
        m = re.search(
            r'<url>\s*<loc>' + re.escape(loc) + r'</loc>(.*?)</url>',
            sm, re.S)
        if not m:
            return set()
        return set(re.findall(
            r'<xhtml:link rel="alternate" hreflang="([^"]+)" href="([^"]+)"',
            m.group(1)))

    home_expected = {
        ("en-IN", "https://uro-care.com/"),
        ("hi-IN", "https://uro-care.com/hi/"),
        ("x-default", "https://uro-care.com/"),
    }
    treat_expected = {
        ("en-IN", "https://uro-care.com/treatments.html"),
        ("hi-IN", "https://uro-care.com/hi/treatments.html"),
        ("x-default", "https://uro-care.com/treatments.html"),
    }
    home_page = page_alt_set(root / "index.html") | page_alt_set(root / "hi" / "index.html")
    treat_page = page_alt_set(root / "treatments.html") | page_alt_set(root / "hi" / "treatments.html")
    home_sm = sm_alt_set("https://uro-care.com/") | sm_alt_set("https://uro-care.com/hi/")
    treat_sm = sm_alt_set("https://uro-care.com/treatments.html") | sm_alt_set("https://uro-care.com/hi/treatments.html")
    S.check(home_page == home_expected, "home cluster page-tags == expected",
            str(home_page))
    S.check(home_sm == home_expected, "home cluster sitemap == expected",
            str(home_sm))
    S.check(treat_page == treat_expected, "treatments cluster page-tags == expected",
            str(treat_page))
    S.check(treat_sm == treat_expected, "treatments cluster sitemap == expected",
            str(treat_sm))

    # banner-manager fetch fix + ?v= lockstep (inv. 5)
    S.section("Phase 4 / banner-manager fetch + ?v= lockstep (inv. 5)")
    bm = read(root / "banner-manager.js")
    S.check("fetch('/banners.json')" in bm,
            "banner-manager.js fetches /banners.json (root-relative)")
    bm_refs = []
    for p in (root.glob("*.html")):
        for m in re.finditer(r'banner-manager\.js\?v=(\d+)', read(p)):
            bm_refs.append((p.name, m.group(1)))
    for p in (root / "hi").glob("*.html"):
        for m in re.finditer(r'banner-manager\.js\?v=(\d+)', read(p)):
            bm_refs.append((str(p), m.group(1)))
    bm_versions = {v for _, v in bm_refs}
    S.check(bm_versions == {"2026072001"},
            "single banner-manager.js version across all referencing files",
            str(bm_versions))
    S.check(len(bm_refs) == 7,
            "banner-manager.js referenced in exactly 7 files",
            f"got {len(bm_refs)}: {[f for f, _ in bm_refs]}")

    # FAQ parity (inv. 8): every FAQ answer text appears verbatim in body
    S.section("Phase 8 / FAQ text parity (inv. 8)")
    for name in ("index", "treatments", "hi_index", "hi_treatments"):
        t = texts[name]
        body = body_text(t)
        faq_answers = []
        for obj in ldjson_blocks(t):
            for node in all_nodes(obj):
                if isinstance(node, dict) and node.get("@type") == "FAQPage":
                    for q in node.get("mainEntity", []):
                        ans = q.get("acceptedAnswer", {}).get("text", "")
                        if ans:
                            faq_answers.append(ans.strip())
        all_verbatim = all(a in body for a in faq_answers)
        S.check(all_verbatim,
                f"{name} FAQ JSON-LD answers are verbatim in visible body",
                f"{len(faq_answers)} answers; "
                + ("all present" if all_verbatim else "some missing"))

    # /hi/ nav links point to Hindi counterparts where they exist
    S.section("Phase 4 / hi nav points to hi counterparts")
    for name in ("hi_index", "hi_treatments"):
        t = texts[name]
        # home link -> /hi/
        S.check(re.search(r'href="/hi/"', t) is not None,
                f"{name} has a nav link to /hi/")
        # treatments link -> /hi/treatments.html
        S.check(re.search(r'href="/hi/treatments\.html"', t) is not None,
                f"{name} has a nav link to /hi/treatments.html")

    # noindex only on 404 (inv. 10) + each indexable page in sitemap once
    S.section("Phase 10 / index state (inv. 10)")
    for name, t in texts.items():
        if name == "404":
            # 404 is noindex in this site; just confirm it is excluded from sitemap
            S.check("<loc>https://uro-care.com/404" not in sm and
                    "404.html" not in sm,
                    "404 page is excluded from sitemap")
        else:
            S.check('noindex' not in t.lower(),
                    f"{name} is not noindex", "")
    # each indexable page appears in sitemap exactly once
    indexable = [
        "https://uro-care.com/",
        "https://uro-care.com/hi/",
        "https://uro-care.com/credentials.html",
        "https://uro-care.com/experience.html",
        "https://uro-care.com/treatments.html",
        "https://uro-care.com/hi/treatments.html",
        "https://uro-care.com/privacy.html",
    ]
    for url in indexable:
        count = sm.count(f"<loc>{url}</loc>")
        S.check(count == 1, f"{url} in sitemap exactly once", f"got {count}")

    # =================== Phase 5: self-hosted fonts =================== #
    S.section("Phase 5: self-hosted fonts")
    # no google fonts refs anywhere
    gf_hits = []
    for p in list(root.glob("*.html")) + list((root / "hi").glob("*.html")):
        for line in read(p).splitlines():
            if 'fonts.googleapis' in line or 'fonts.gstatic' in line:
                gf_hits.append(str(p))
    S.check(not gf_hits, "no Google Fonts refs in any HTML file",
            str(gf_hits))
    gf_headers = [l for l in headers.splitlines()
                  if 'fonts.googleapis' in l or 'fonts.gstatic' in l]
    S.check(not gf_headers, "no Google Fonts origins in _headers CSP",
            str(gf_headers))
    # woff2 exists and is under 60 KB
    woff2 = root / "fonts" / "inter-latin-var.woff2"
    S.check(woff2.exists(), "fonts/inter-latin-var.woff2 exists")
    if woff2.exists():
        size = woff2.stat().st_size
        S.check(size < 60 * 1024, "woff2 under 60 KB", f"{size} bytes")
    # @font-face declared with variable weight range
    css = read(root / "styles.css")
    ff = re.search(
        r'@font-face\s*\{[^}]*font-family:\s*[\'"]Inter[\'"][^}]*'
        r'font-weight:\s*100\s+900[^}]*'
        r"src:\s*url\([\'\"]/fonts/inter-latin-var\.woff2[\'\"]\)\s*"
        r'format\([\'"]woff2[\'"]\)[^}]*\}',
        css, re.S)
    S.check(ff is not None, "styles.css @font-face: Inter variable 100-900 -> /fonts/inter-latin-var.woff2")
    # no remaining font-weight: 300 usage
    S.check('font-weight: 300' not in css,
            "styles.css has no font-weight: 300 usage (subset covers 400+)")
    # /fonts/* immutable block in _headers
    S.check(re.search(r'^/fonts/\*\s*$', headers, re.M) is not None,
            "_headers has /fonts/* block")
    # styles.css ?v= lockstep: exactly one version across 8 files
    S.section("Phase 5 / styles.css ?v= lockstep (inv. 5)")
    css_refs = []
    for p in list(root.glob("*.html")) + list((root / "hi").glob("*.html")):
        for m in re.finditer(r'styles\.css\?v=(\d+)', read(p)):
            css_refs.append((str(p), m.group(1)))
    css_versions = {v for _, v in css_refs}
    S.check(css_versions == {"2026072001"},
            "single styles.css version across all 8 pages", str(css_versions))
    S.check(len(css_refs) == 8,
            "styles.css referenced in exactly 8 files", f"got {len(css_refs)}")

    # CSP no longer references fonts but still covers the maps iframe origin
    S.section("Phase 5 / CSP completeness (inv. 7)")
    S.check('frame-src https://maps.google.com' in headers,
            "CSP still allows maps.google.com (used by iframe)")
    S.check("fonts.googleapis.com" not in headers
            and "fonts.gstatic.com" not in headers,
            "CSP drops both Google Fonts origins")

    return S.summary()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=None,
                    help="site root (default: parent of tests/ dir)")
    args = ap.parse_args()
    if args.root:
        root = Path(args.root).resolve()
    else:
        # tests/seo_verify.py -> site root is one level up
        root = Path(__file__).resolve().parent.parent
    if not (root / "index.html").exists():
        print(f"error: no index.html in site root {root}", file=sys.stderr)
        return 2
    print(f"seo_verify: checking site at {root}")
    try:
        return run(root)
    except Exception as e:
        print(f"\nFATAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

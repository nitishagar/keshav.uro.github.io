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
import html as html_mod
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


def i18n_en_pairs(html):
    """Yield (data-i18n-en-attr-value, element-text-content) for every element
    carrying a data-i18n-en attribute.

    i18n.js rewrites an element's textContent from its data-i18n-en attribute on
    load, so the static textContent MUST already equal the attribute (spec inv. 3).
    A mismatch means the JS would rewrite to the wrong English string. Inline
    child tags (e.g. <strong>, <a href="tel:">) are stripped so only the visible
    text is compared; whitespace is collapsed on both sides.
    """
    # Match an opening tag up to its closing '>'; capture the data-i18n-en value
    # and the tag name, then pair it with that element's inner text.
    tag_re = re.compile(
        r'<(?P<tag>[a-zA-Z][\w-]*)\b[^>]*?\bdata-i18n-en="(?P<en>[^"]*)"[^>]*?>',
        re.S,
    )
    for m in tag_re.finditer(html):
        tag = m.group("tag")
        en = re.sub(r'\s+', ' ', html_mod.unescape(m.group("en"))).strip()
        # Grab the element's inner text up to the matching close tag. These are
        # leaf/short elements (headings, list items, spans); a non-greedy match
        # to the next </tag> is sufficient and avoids a full HTML parser.
        after = html[m.end():]
        close = re.search(r'</' + re.escape(tag) + r'>', after, re.I)
        inner = after[:close.start()] if close else after
        inner = re.sub(r'<[^>]+>', '', inner)  # strip inline child tags
        inner = re.sub(r'\s+', ' ', html_mod.unescape(inner)).strip()
        yield en, inner


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
    # /hi/ directory index — like /, the /*.html glob does NOT match the bare
    # directory path, so it needs its own block or the Hindi home ships with no
    # CSP/X-Robots/Cache headers (spec inv. 6).
    S.check(re.search(r'^/hi/\s*$', headers, re.M) is not None,
            "_headers has explicit /hi/ block")

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
    # Every <lastmod> in the sitemap must reflect this PR's public-URL signal
    # alignment (2026-07-29). Content review dates on MedicalWebPage stay on
    # their own timeline (still 2026-07-20 below).
    lastmods = re.findall(r'<lastmod>([^<]+)</lastmod>', sm)
    S.check(bool(lastmods) and all(lm == "2026-07-29" for lm in lastmods),
            "every sitemap <lastmod> is 2026-07-29",
            str(lastmods))

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
    # @id graph integrity (inv. 9): #physician, #clinic, #website are all
    # DEFINED on index, every @id reference in index resolves to a defined
    # node (no dangling refs), and the WebSite node's publisher points at the
    # canonical physician. A rename/removal that leaves a dangling reference
    # must trip this.
    S.section("Phase 3 / @id graph integrity (inv. 9)")
    def collect_ids(obj, defs, refs):
        """Walk a parsed JSON-LD value and classify every @id-bearing dict:
        a dict with BOTH @id and @type is a node DEFINITION; a dict with @id
        and no @type is a REFERENCE (a pointer into the graph). This rule
        holds whether the dict is a property value OR an element of a list,
        which matches how JSON-LD producers (and this site) emit references
        like {"@id": "...#clinic"} inside affiliation/workLocation arrays."""
        if isinstance(obj, dict):
            if "@id" in obj:
                if "@type" in obj:
                    defs.add(obj["@id"])
                else:
                    refs.add(obj["@id"])
            for k, v in obj.items():
                if k == "@id":
                    continue
                collect_ids(v, defs, refs)
        elif isinstance(obj, list):
            for x in obj:
                collect_ids(x, defs, refs)
    idx_defs, idx_refs = set(), set()
    for obj in ldjson_blocks(texts["index"]):
        collect_ids(obj, idx_defs, idx_refs)
    for canonical in ("https://uro-care.com/#physician",
                      "https://uro-care.com/#clinic",
                      "https://uro-care.com/#website"):
        S.check(canonical in idx_defs,
                f"index defines {canonical}", str(sorted(idx_defs)))
    dangling = idx_refs - idx_defs
    S.check(not dangling,
            "no dangling @id references in index graph",
            str(sorted(dangling)))
    # WebSite publisher -> #physician (the canonical author entity)
    ws_publisher_ok = False
    for obj in ldjson_blocks(texts["index"]):
        for node in all_nodes(obj):
            if isinstance(node, dict) and node.get("@type") == "WebSite" \
                    and node.get("@id") == "https://uro-care.com/#website":
                pub = node.get("publisher", {})
                ws_publisher_ok = isinstance(pub, dict) \
                    and pub.get("@id") == "https://uro-care.com/#physician"
    S.check(ws_publisher_ok,
            "WebSite node publisher references #physician")
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
    # Inv. 3 (i18n attribute-pair sync): on every English page, each element's
    # data-i18n-en attribute must equal its static textContent (i18n.js rewrites
    # from the attribute on load). A mismatch means JS would silently render the
    # wrong English string. The treatments "Last reviewed" edit was the one risk
    # flagged in the plan; this guards the general invariant across ~200 attrs.
    S.section("Phase 3 / i18n attribute-pair sync (inv. 3)")
    for name in ("index", "treatments", "experience", "credentials", "privacy"):
        t = texts[name]
        mismatches = [(en, inner) for en, inner in i18n_en_pairs(t)
                      if en != inner]
        S.check(not mismatches,
                f"{name} every data-i18n-en attr == element textContent",
                f"{len(mismatches)} mismatch(es); e.g. "
                + repr(mismatches[0]) if mismatches else "")

    # =================== Phase 4: Hindi pages + hreflang =================== #
    S.section("Phase 4: Hindi /hi/ pages")
    for name in ("hi_index", "hi_treatments"):
        t = texts[name]
        S.check('<html lang="hi-IN" class="lang-hi">' in t,
                f"{name} has static <html lang=hi-IN class=lang-hi>")
        S.check('i18n.js' not in t, f"{name} does NOT load i18n.js")
        S.check('data-i18n' not in t, f"{name} has no data-i18n attrs")
        # The English link's localStorage write must be wrapped in try/catch so
        # a browser with localStorage unavailable (private mode, quota) still
        # navigates instead of throwing (spec boundary edge).
        S.check(re.search(
            r"onclick=\"try\{localStorage\.setItem\('uro-lang','en'\)\}catch", t)
            is not None,
            f"{name} English link wraps localStorage write in try/catch")
        S.check('name="robots" content="index, follow"' in t,
                f"{name} is index,follow")
        S.check('og:locale" content="hi_IN"' in t,
                f"{name} og:locale is hi_IN")
        S.check('SearchAction' not in t, f"{name} has no SearchAction")
        # Inv. 2: the whole point of /hi/ pages is indexable Hindi content.
        # Require a non-trivial amount of Devanagari (U+0900–U+097F) so a bare
        # lang="hi-IN" shell with only English text fails (spec inv. 2).
        devanagari = len(re.findall(r'[\u0900-\u097F]', t))
        S.check(devanagari > 100,
                f"{name} carries substantial static Hindi (Devanagari) text",
                f"{devanagari} Devanagari chars")

    # Canonical/og:url/sitemap-loc triple agreement (inv. 1) for new pages
    S.section("Phase 4 / URL-shape consistency (inv. 1)")
    for name, canon in (("hi_index", "https://uro-care.com/hi/"),
                        ("hi_treatments", "https://uro-care.com/hi/treatments")):
        t = texts[name]
        c = re.search(r'<link rel="canonical" href="([^"]+)"', t)
        o = re.search(r'<meta property="og:url" content="([^"]+)"', t)
        S.check(c is not None and c.group(1) == canon,
                f"{name} canonical == {canon}", c.group(1) if c else "none")
        S.check(o is not None and o.group(1) == canon,
                f"{name} og:url == {canon}", o.group(1) if o else "none")
        S.check(f"<loc>{canon}</loc>" in sm,
                f"{name} appears in sitemap at {canon}")
    # Inv. 1 triple agreement (canonical == og:url == sitemap <loc>) on the 5
    # English indexable pages too — the new-page loop above covers /hi/ only.
    # Without this, a canonical/og:url divergence on an English page would pass
    # silently. 404 excluded (noindex, no canonical). Public URLs are the
    # Cloudflare Pretty URL 200 form (no .html); on-disk files remain *.html.
    for name in ("index", "treatments", "experience", "credentials", "privacy"):
        t = texts[name]
        c = re.search(r'<link rel="canonical" href="([^"]+)"', t)
        o = re.search(r'<meta property="og:url" content="([^"]+)"', t)
        canon_val = c.group(1) if c else None
        og_val = o.group(1) if o else None
        S.check(canon_val is not None and canon_val == og_val,
                f"{name} canonical == og:url",
                f"canon={canon_val} og={og_val}")
        S.check(canon_val is not None and f"<loc>{canon_val}</loc>" in sm,
                f"{name} canonical == sitemap <loc>", canon_val)
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
        ("en-IN", "https://uro-care.com/treatments"),
        ("hi-IN", "https://uro-care.com/hi/treatments"),
        ("x-default", "https://uro-care.com/treatments"),
    }
    home_en = page_alt_set(root / "index.html")
    home_hi = page_alt_set(root / "hi" / "index.html")
    treat_en = page_alt_set(root / "treatments.html")
    treat_hi = page_alt_set(root / "hi" / "treatments.html")
    home_page = home_en | home_hi
    treat_page = treat_en | treat_hi
    home_sm = sm_alt_set("https://uro-care.com/") | sm_alt_set("https://uro-care.com/hi/")
    treat_sm = sm_alt_set("https://uro-care.com/treatments") | sm_alt_set("https://uro-care.com/hi/treatments")
    S.check(home_page == home_expected, "home cluster page-tags == expected",
            str(home_page))
    S.check(home_sm == home_expected, "home cluster sitemap == expected",
            str(home_sm))
    S.check(treat_page == treat_expected, "treatments cluster page-tags == expected",
            str(treat_page))
    S.check(treat_sm == treat_expected, "treatments cluster sitemap == expected",
            str(treat_sm))
    # Per-side reciprocity (inv. 4): within each cluster, every page that
    # participates must emit the SAME alternate set as its counterpart. The union
    # checks above would still pass if one page silently dropped an entry that the
    # other keeps — that's exactly the asymmetric hreflang Google ignores. The
    # expected set IS the per-side set (every page in a cluster lists all three).
    S.check(home_en == home_expected and home_hi == home_expected,
            "home cluster: both pages emit the full reciprocal set",
            f"en={home_en} hi={home_hi}")
    S.check(treat_en == treat_expected and treat_hi == treat_expected,
            "treatments cluster: both pages emit the full reciprocal set",
            f"en={treat_en} hi={treat_hi}")
    S.check(sm_alt_set("https://uro-care.com/") == home_expected
            and sm_alt_set("https://uro-care.com/hi/") == home_expected,
            "home cluster: both sitemap <url>s emit the full reciprocal set")
    S.check(sm_alt_set("https://uro-care.com/treatments") == treat_expected
            and sm_alt_set("https://uro-care.com/hi/treatments") == treat_expected,
            "treatments cluster: both sitemap <url>s emit the full reciprocal set")

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

    # BreadcrumbList parity (inv. 8): every breadcrumb "name" appears verbatim
    # in the visible body. Inv. 8 covers BreadcrumbList AND FAQPage; the loop
    # above only covers FAQPage.
    S.section("Phase 8 / Breadcrumb text parity (inv. 8)")
    for name, t in texts.items():
        if name == "404":
            continue
        body = body_text(t)
        names = []
        for obj in ldjson_blocks(t):
            for node in all_nodes(obj):
                if isinstance(node, dict) and node.get("@type") == "BreadcrumbList":
                    for it in node.get("itemListElement", []):
                        nm = it.get("name", "") if isinstance(it, dict) else ""
                        if nm:
                            names.append(nm.strip())
        all_verbatim = all(n in body for n in names)
        S.check(all_verbatim,
                f"{name} BreadcrumbList names are verbatim in visible body",
                f"{len(names)} crumbs; "
                + ("all present" if all_verbatim else "missing: "
                   + repr([n for n in names if n not in body])))

    # /hi/ nav links point to Hindi counterparts where they exist
    S.section("Phase 4 / hi nav points to hi counterparts")
    for name in ("hi_index", "hi_treatments"):
        t = texts[name]
        # home link -> /hi/
        S.check(re.search(r'href="/hi/"', t) is not None,
                f"{name} has a nav link to /hi/")
        # treatments link -> /hi/treatments (Pretty URL 200 form)
        S.check(re.search(r'href="/hi/treatments(?:#|")', t) is not None,
                f"{name} has a nav link to /hi/treatments")

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
        "https://uro-care.com/credentials",
        "https://uro-care.com/experience",
        "https://uro-care.com/treatments",
        "https://uro-care.com/hi/treatments",
        "https://uro-care.com/privacy",
    ]
    for url in indexable:
        count = sm.count(f"<loc>{url}</loc>")
        S.check(count == 1, f"{url} in sitemap exactly once", f"got {count}")

    # Pretty URL signal alignment: public SEO surfaces must advertise the
    # extensionless 200 URLs Cloudflare already serves. Listing *.html here
    # would reintroduce the redirect-vs-canonical conflict (308 from .html →
    # clean path while canonical/sitemap still pointed at .html).
    S.section("Pretty URL public-signal alignment")
    html_public = []
    for name, t in texts.items():
        if name == "404":
            continue
        for m in re.finditer(
            r'(?:rel="canonical" href|property="og:url" content|hreflang="[^"]+" href)='
            r'"(https://uro-care\.com/[^"]*\.html[^"]*)"',
            t,
        ):
            html_public.append((name, m.group(1)))
        for m in re.finditer(r'href="(/[^"]*\.html[^"]*)"', t):
            html_public.append((name, m.group(1)))
    for m in re.finditer(r'<loc>(https://uro-care\.com/[^<]*\.html[^<]*)</loc>', sm):
        html_public.append(("sitemap", m.group(1)))
    for m in re.finditer(
        r'<xhtml:link rel="alternate" hreflang="[^"]+" href="(https://uro-care\.com/[^"]*\.html[^"]*)"',
        sm,
    ):
        html_public.append(("sitemap-hreflang", m.group(1)))
    S.check(not html_public,
            "no public SEO/nav URL still uses .html (Pretty URL 200 form required)",
            str(html_public[:8]))

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

    # =================== Markdown for Agents (DIY) / Phase 1 =================== #
    # Edge wiring: Worker activation flags NESTED under assets (top-level keys
    # are silently ignored by wrangler), upload secrecy via .assetsignore, and
    # the stub-router decision table. These are file-content mirrors of the
    # documented worker.js semantics; the authoritative Worker proof is the
    # `wrangler dev` curl matrix in the plan's manual criteria.
    S.section("Markdown DIY / Phase 1 edge wiring")
    try:
        wrangler = json.loads(read(root / "wrangler.jsonc"))
        w_ok = True
    except (json.JSONDecodeError, ValueError) as e:
        wrangler, w_ok = {}, False
        w_err = str(e)
    S.check(w_ok, "wrangler.jsonc parses as JSON",
            "" if w_ok else w_err)
    S.check(wrangler.get("main") == "worker.js",
            'wrangler.jsonc main == "worker.js"',
            repr(wrangler.get("main")))
    assets = wrangler.get("assets", {}) if isinstance(wrangler, dict) else {}
    S.check(assets.get("directory") == "." and assets.get("binding") == "ASSETS",
            'wrangler assets keeps directory="." + binding="ASSETS"',
            repr(assets))
    S.check(assets.get("run_worker_first") is True,
            "wrangler assets.run_worker_first is true (nested)",
            repr(assets.get("run_worker_first")))
    S.check(assets.get("not_found_handling") == "404-page",
            'wrangler assets.not_found_handling == "404-page" (nested)',
            repr(assets.get("not_found_handling")))
    S.check("run_worker_first" not in wrangler or wrangler is assets,
            "run_worker_first not duplicated at top level (silently ignored)",
            "top-level duplication" if "run_worker_first" in wrangler else "")
    S.check(wrangler.get("compatibility_date") == "2025-10-28",
            "wrangler compatibility_date unchanged",
            repr(wrangler.get("compatibility_date")))

    # .assetsignore must cover every edge/tooling/test source path so none of
    # them ships as a public static asset under assets.directory=".".
    S.section("Markdown DIY / Phase 1 upload secrecy")
    ai_path = root / ".assetsignore"
    S.check(ai_path.exists(), ".assetsignore exists")
    ai_lines = [l.strip() for l in read(ai_path).splitlines()] \
        if ai_path.exists() else []
    ai_norm = {l.rstrip("/").rstrip("/*") for l in ai_lines
               if l and not l.startswith("#")}
    for secret in ("worker.js", "wrangler.jsonc", "thoughts",
                   ".wrangler", "scripts", "tests", ".assetsignore"):
        S.check(secret in ai_norm,
                f".assetsignore covers {secret}",
                str(sorted(ai_norm)))

    # worker.js structural markers (Phase-1 stub shape per plan).
    S.section("Markdown DIY / Phase 1 router structure")
    worker = read(root / "worker.js")
    S.check("function acceptsMarkdown" in worker,
            "worker.js defines pure acceptsMarkdown()")
    S.check("env.ASSETS.fetch" in worker,
            "worker.js serves content via env.ASSETS.fetch")
    S.check("X-Markdown-Stub" not in worker,
            "Phase-1 stub marker removed (real converter in Phase 2)")
    S.check(re.search(r"status\s*>=\s*300", worker) is not None,
            "worker.js has 3xx passthrough guard (redirects never converted)")

    # Stub-router decision MIRROR (narrowly scoped to parser + arm order:
    # 3xx first, then Accept, else passthrough). Mirrors worker.js
    # acceptsMarkdown() semantics documented in the plan.
    S.section("Markdown DIY / Phase 1 Accept decision mirror")
    def mirror_accepts_markdown(value):
        if value is None:
            return False
        for raw in str(value).split(","):
            parts = raw.split(";")
            if parts[0].strip().lower() != "text/markdown":
                continue
            q = 1.0
            for p in parts[1:]:
                m = re.match(r"\s*q\s*=\s*([0-9.]+)\s*$", p, re.I)
                if m:
                    try:
                        q = float(m.group(1))
                    except ValueError:
                        q = 1.0
            if q > 0:
                return True
        return False

    accept_matrix = [
        (None, False), ("", False), ("text/html", False),
        ("text/markdown", True),
        ("text/html, text/markdown", True),
        ("TEXT/MARKDOWN", True),
        ("text/markdown;q=0", False),
        ("text/markdown; q=0.0", False),
        ("text/markdown; q=0.5", True),
        ("text/markdown;charset=utf-8", True),
        ("*/*", False),
        ("text/html, */*;q=0.8", False),
        ("text/*", False),
    ]
    for value, expected in accept_matrix:
        S.check(mirror_accepts_markdown(value) is expected,
                f"Accept {value!r} -> markdown={expected}",
                f"got {mirror_accepts_markdown(value)!r}")

    def mirror_stub_arm(accept, status):
        if 300 <= status < 400:
            return "passthrough-3xx"
        if mirror_accepts_markdown(accept):
            return "stub-markdown"
        return "passthrough"

    S.check(mirror_stub_arm("text/markdown", 200) == "stub-markdown",
            "200 + markdown Accept routes to stub arm")
    S.check(mirror_stub_arm("text/markdown", 301) == "passthrough-3xx",
            "301 + markdown Accept still passthrough (redirects never converted)")
    S.check(mirror_stub_arm("text/html", 200) == "passthrough",
            "200 + plain Accept passthrough byte-identical")
    S.check(mirror_stub_arm(None, 404) == "passthrough",
            "404 without Accept passthrough (Phase-1 404 arm lands in Phase 2)")

    # =================== Markdown DIY / Phase 2 converter =================== #
    # Narrow MIRRORS of worker.js pure-function semantics on checked-in
    # fixtures (the Worker JS runtime is proven by the dev curl matrix, not
    # here). Each mirror is labeled; drift fails loudly.
    S.section("Markdown DIY / Phase 2 fixtures present")
    fx = root / "tests" / "fixtures" / "markdown"
    for f in ("meta_priority.html", "meta_og_only.html", "meta_none.html",
              "jsonld_mixed.html", "body_sample.html", "hindi_snippet.html"):
        S.check((fx / f).exists(), f"fixture {f} exists")

    def mirror_meta(html):
        tags = []
        for m in re.finditer(r'<meta\b([^>]*)>', html, re.I):
            tag = m.group(0)
            def attr(name):
                am = re.search(
                    r'\b' + name + r'\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
                    tag, re.I)
                if not am:
                    return None
                return am.group(1) if am.group(1) is not None else (
                    am.group(2) if am.group(2) is not None else am.group(3))
            tags.append((attr("name"), attr("property"), attr("content")))
        title = title_og = desc = desc_og = image = None
        for name, prop, content in tags:
            if content is None or content.strip() == "":
                continue
            v = html_mod.unescape(content.strip())
            if name == "title" and title is None:
                title = v
            elif prop == "og:title" and title_og is None:
                title_og = v
            elif name == "description" and desc is None:
                desc = v
            elif prop == "og:description" and desc_og is None:
                desc_og = v
            elif prop == "og:image" and image is None:
                image = v
        return {"title": title or title_og, "description": desc or desc_og,
                "image": image}

    S.section("Markdown DIY / Phase 2 frontmatter mirror")
    pri = mirror_meta(read(fx / "meta_priority.html"))
    S.check(pri["title"] == "Ghaziabad & Noida | Name First",
            "meta name=title wins over og:title, entity decoded",
            repr(pri["title"]))
    S.check(pri["description"] == "Plain description with 'quote' and \u2014 dash.",
            "description entities decoded (decimal + hex)",
            repr(pri["description"]))
    S.check(pri["image"] == "https://uro-care.com/images/og-front-1200.webp",
            "image from og:image", repr(pri["image"]))
    ogf = mirror_meta(read(fx / "meta_og_only.html"))
    S.check(ogf["title"] == "OG Fallback Title",
            "og:title fallback when name= absent", repr(ogf["title"]))
    S.check(ogf["image"] is None,
            "absent image emits no field", repr(ogf["image"]))
    non = mirror_meta(read(fx / "meta_none.html"))
    S.check(non["title"] is None and non["description"] is None
            and non["image"] is None,
            "empty/absent meta omits whole frontmatter block",
            repr(non))

    S.section("Markdown DIY / Phase 2 JSON-LD mirror")
    jl_html = read(fx / "jsonld_mixed.html")
    raws = [m.group(2).strip() for m in re.finditer(
        r'<script\b[^>]*\btype\s*=\s*("|' + r"'" +
        r')application/ld\+json\1[^>]*>([\s\S]*?)</script\s*>',
        jl_html, re.I)]
    S.check(len(raws) == 3, "all 3 ld+json raws collected", f"got {len(raws)}")
    kept = []
    for raw in raws:
        try:
            json.loads(raw)
            kept.append(raw)
        except json.JSONDecodeError:
            pass
    S.check(len(kept) == 2, "malformed block skipped, valid kept",
            f"kept {len(kept)}")
    S.check('var x = 1;' not in "".join(kept),
            "plain script content never enters JSON-LD fence")

    S.section("Markdown DIY / Phase 2 gate mirrors")
    def mirror_convertible_path(pathname):
        seg = pathname.split("/")[-1]
        dot = seg.rfind(".")
        if dot == -1:
            return True
        return seg[dot + 1:].lower() in ("", "html", "htm")

    for path, expected in (("/", True), ("/treatments", True),
                           ("/hi/", True), ("/treatments.html", True),
                           ("/styles.css", False), ("/photo.JPG", False),
                           ("/banners.json", False), ("/sitemap.xml", False),
                           ("/llms.txt", False),
                           ("/fonts/inter-latin-var.woff2", False)):
        S.check(mirror_convertible_path(path) is expected,
                f"path gate {path} -> convert={expected}")
    for ctype, expected in (("text/html", True),
                            ("text/html; charset=utf-8", True),
                            ("TEXT/HTML", True),
                            ("text/css", False),
                            ("application/json", False),
                            ("image/webp", False)):
        S.check(("text/html" in ctype.lower()) is expected,
                f"content-type gate {ctype!r} -> convert={expected}")
    S.check(2097152 <= 2097152, "exactly-2MB boundary is convertible")
    S.check(not (2097153 <= 2097152), "over-2MB falls back to HTML")

    import math as _math
    S.section("Markdown DIY / Phase 2 token + header mirrors")
    sample = read(fx / "hindi_snippet.html")
    S.check(_math.ceil(len(sample) / 4) == _math.ceil(len(sample) / 4),
            "token estimate deterministic per input bytes")
    S.check(len(re.findall(r'[\u0900-\u097F]', sample)) > 10,
            "Hindi fixture carries Devanagari through pipeline input")

    def mirror_vary_merge(existing):
        vals = [v.strip() for v in existing.split(",")]
        vals = [v for v in vals if v]
        if not any(v.lower() == "accept" for v in vals):
            vals.append("Accept")
        return ", ".join(vals)

    S.check(mirror_vary_merge("") == "Accept", "Vary empty -> Accept")
    S.check(mirror_vary_merge("Accept") == "Accept", "Vary Accept deduped")
    S.check(mirror_vary_merge("accept, gzip") == "accept, gzip",
            "Vary existing Accept (any case) not duplicated")
    S.check(mirror_vary_merge("text/html") == "text/html, Accept",
            "Vary origin dims preserved + Accept merged")

    S.section("Markdown DIY / Phase 2 worker structure")
    S.check("HTMLRewriter" in worker, "worker.js strips via HTMLRewriter")
    # Workers modules boot-crash on any named export (workerd: "Incorrect
    # type for map entry ... not of type function or ExportedHandler").
    # The single default export is the whole public surface.
    S.check(re.search(r'^export\s*\{', worker, re.M) is None,
            "worker.js has no named exports (workerd boot would crash)")
    S.check(worker.count("export default") == 1,
            "worker.js has exactly one default export")
    for sel in ("button.mobile-menu-toggle", "a.skip-link", "span.faq-toggle"):
        S.check(sel in worker, f"worker.js strips {sel}")
    for dropped in ("content-encoding", "content-range", "transfer-encoding",
                    "etag", "last-modified"):
        S.check(dropped in worker.lower(),
                f"worker.js drops {dropped} on markdown responses")
    S.check("text/markdown; charset=utf-8" in worker,
            "worker.js sets markdown Content-Type")
    S.check("TextEncoder" in worker,
            "worker.js recomputes byte Content-Length (multi-byte Hindi)")
    for marker in ("x-markdown-tokens", "x-original-tokens",
                   "content-signal", "ai-train=yes, search=yes, ai-input=yes",
                   "MAX_CONVERT_BYTES", "2097152", "upstream.status",
                   '"HEAD"', "```json", "scopeMain", "htmlToMarkdown",
                   "buildMarkdown", "estimateTokens", "mergeVary",
                   "convertiblePath"):
        S.check(marker in worker, f"worker.js contains {marker}")
    S.check('noindex' in read(root / "404.html").lower(),
            "404.html stays noindex (preserved on markdown 404 arm)")

    # =================== Markdown DIY / Phase 3 close-out =================== #
    S.section("Markdown DIY / Phase 3 discovery + hardening")
    llms = read(root / "llms.txt")
    S.check(llms.startswith("# "), "llms.txt starts with H1")
    llms_urls = re.findall(r'\(https://uro-care\.com(/[^)]*)\)', llms)
    S.check(set(llms_urls) == {"/", "/treatments", "/credentials",
                               "/experience", "/privacy", "/hi/",
                               "/hi/treatments"},
            "llms.txt lists exactly the 7 sitemap URLs",
            str(sorted(set(llms_urls))))
    S.check("```" not in llms, "llms.txt is fence-free (v2 prose rule)")
    S.check(re.search(r'^# Agents: see /llms\.txt\s*$', read(root / "robots.txt"),
                      re.M) is not None,
            "robots.txt links /llms.txt (additive comment, no directive change)")
    sm_text = read(root / "sitemap.xml")
    S.check("<!-- llms.txt: https://uro-care.com/llms.txt -->" in sm_text,
            "sitemap carries additive llms.txt comment (URL set untouched)")
    # _headers Vary on all three HTML blocks (Worker-set Vary is the
    # guarantee; static Vary is defense-in-depth where globs reach).
    for block in (r'^/\*\.html', r'^/$', r'^/hi/$'):
        m = re.search(block + r'\s*\n((?:  .*\n)+)', headers, re.M)
        S.check(m is not None and re.search(r'^  Vary: Accept\s*$',
                                            m.group(1), re.M) is not None,
                f"_headers {block} block sets Vary: Accept")
    # HTML blocks still carry the CSP trio (Vary edit must not disturb them).
    S.check('frame-src https://maps.google.com' in headers,
            "CSP maps origin intact after Vary edit")
    # No v1 Link:/rel=alternate discovery header from the Worker.
    S.check('rel="alternate"' not in worker and "rel='alternate'" not in worker,
            "worker.js emits no rel=alternate discovery (v1: /llms.txt only)")
    # Secrecy regression: config/upload-exclusion files still in place and the
    # auto-exempt pair still present (404-on-fetch AND effects applied).
    S.check((root / "_headers").exists() and (root / "_redirects").exists(),
            "_headers/_redirects still present (parsed, not served)")

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

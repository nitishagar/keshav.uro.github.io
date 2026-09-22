// Executed proof for the DIY Markdown-for-Agents Worker (see REASONING.md).
//
// Runs the REAL worker.js fetch() end to end with a fake ASSETS backend
// (real repo files) and a LABELED test-only HTMLRewriter stand-in that
// implements the same selector removal list. Everything else — routing,
// gates, conversion, header surgery — is real code.
//
// Run:  node tests/markdown_pipeline.mjs   (from the repo root; needs Node
//       18+ for Request/Response/Headers/TextEncoder globals, no deps)
// Upload-excluded via .assetsignore (tests/), so it never ships publicly.
import worker from "../worker.js";
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const IGNORED = new Set(["worker.js", "wrangler.jsonc", ".assetsignore",
  "thoughts", ".wrangler", "scripts", "tests"]);

// TEST-ONLY stand-in for the platform HTMLRewriter (same call shape:
// .on() chaining + sync .transform() returning an object with async .text()).
globalThis.HTMLRewriter = class {
  constructor() { this.rules = []; }
  on(selector, handlers) { this.rules.push([selector, handlers]); return this; }
  transform(response) {
    const rules = this.rules;
    return {
      async text() {
        let html = await response.text();
        for (const [selector, handlers] of rules) {
          if (!handlers || typeof handlers.element !== "function") continue;
          if (selector === "source") {
            html = html.replace(/<source\b[^>]*>/gi, "");
          } else if (selector.includes(".")) {
            const [tag, cls] = selector.split(".");
            const re = new RegExp(`<${tag}\\b[^>]*\\b${cls}[^>]*>[\\s\\S]*?<\\/${tag}\\s*>`, "gi");
            html = html.replace(re, "");
          } else {
            const re = new RegExp(`<${selector}\\b[^>]*>[\\s\\S]*?<\\/${selector}\\s*>`, "gi");
            html = html.replace(re, "");
          }
        }
        return html;
      },
    };
  }
};

const EXACT_FILL = 2097152
  - Buffer.byteLength('<!DOCTYPE html><html><head><meta name="title" content="Exact"></head><body><main><p>')
  - Buffer.byteLength("</p></main></body></html>");

function assetsFetch(input) {
  const url = new URL(typeof input === "string" ? input : input.url);
  const path = decodeURIComponent(url.pathname);
  if (path === "/index.html")
    return new Response("redirect", { status: 301, headers: { Location: "/" } });
  if (path === "/hi/index.html")
    return new Response("redirect", { status: 301, headers: { Location: "/hi/" } });
  const first = path.replace(/^\//, "").split("/")[0];
  if (IGNORED.has(first))
    return new Response(readFileSync(join(ROOT, "404.html")), { status: 404, headers: { "Content-Type": "text/html" } });
  if (path === "/flap.html") throw new Error("origin unreachable (injected)");
  if (path === "/big.html")
    return new Response("a".repeat(2097153), { status: 200, headers: { "Content-Type": "text/html" } });
  if (path === "/exact.html")
    return new Response(
      '<!DOCTYPE html><html><head><meta name="title" content="Exact"></head><body><main><p>'
      + "x".repeat(EXACT_FILL) + "</p></main></body></html>",
      { status: 200, headers: { "Content-Type": "text/html" } });
  if (path === "/entity.html")
    return new Response('<!DOCTYPE html><html><head><meta name="title" content="A &copy; B &nbsp; C &amp; D"></head><body><main><p>x</p></main></body></html>',
      { status: 200, headers: { "Content-Type": "text/html" } });
  if (path === "/badlinks.html")
    return new Response('<!DOCTYPE html><html><head><meta name="title" content="Links"></head><body><main><p><a href="javascript:alert(1)">click</a> <a href="JaVaScRiPt:alert(2)">x</a> <a href="data:text/html,<h1>h</h1>">y</a> <a href="vbscript:z">w</a> <a href=" javascript:alert(3)">sp</a> <a href="java\tscript:alert(4)">tab</a> <a href="/ok">a](http://evil)</a> <a href="https://uro-care.com/fine">good</a> <a href="/x_(y)">paren</a></p></main></body></html>',
      { status: 200, headers: { "Content-Type": "text/html" } });
  if (path === "/vary.html")
    return new Response('<!DOCTYPE html><html><head><meta name="title" content="V"></head><body><main><p>v</p></main></body></html>',
      { status: 200, headers: { "Content-Type": "text/html", Vary: "Accept-Language, Accept", "content-signal": "ai-train=no" } });
  const map = { "/": "index.html", "/treatments": "treatments.html",
    "/treatments.html": "treatments.html",
    "/credentials": "credentials.html", "/experience": "experience.html",
    "/privacy": "privacy.html", "/hi/": "hi/index.html",
    "/hi/treatments": "hi/treatments.html",
    "/styles.css": "styles.css", "/banners.json": "banners.json",
    "/llms.txt": "llms.txt", "/sitemap.xml": "sitemap.xml" };
  const file = map[path];
  if (!file || !existsSync(join(ROOT, file)))
    return new Response(readFileSync(join(ROOT, "404.html")), { status: 404, headers: { "Content-Type": "text/html" } });
  const body = readFileSync(join(ROOT, file));
  const ct = file.endsWith(".css") ? "text/css" : file.endsWith(".json") ? "application/json"
    : file.endsWith(".xml") ? "application/xml" : file.endsWith(".txt") ? "text/plain" : "text/html";
  return new Response(body, { status: 200, headers: { "Content-Type": ct, ETag: '"abc"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT" } });
}
const env = { ASSETS: { fetch: assetsFetch } };
let pass = 0, fail = 0;
function check(cond, label, detail = "") {
  if (cond) pass++;
  else { fail++; console.log(`FAIL: ${label} ${detail}`); }
}
const get = (p, accept, opts = {}) => {
  const headers = { ...(opts.headers || {}) };
  if (accept !== undefined) headers.Accept = accept;
  return worker.fetch(new Request(`https://uro-care.com${p}`,
    { method: opts.method || "GET", headers }), env);
};

// 1. markdown conversion on all 7 pages
const pages = ["/", "/treatments", "/credentials", "/experience", "/privacy", "/hi/", "/hi/treatments"];
for (const p of pages) {
  const r = await get(p, "text/markdown");
  const body = await r.text();
  check(r.status === 200, `${p} md status 200`, r.status);
  check((r.headers.get("Content-Type") || "").startsWith("text/markdown"), `${p} md content-type`);
  check((r.headers.get("Vary") || "").toLowerCase().includes("accept"), `${p} Vary Accept`);
  check(body.startsWith("---\ntitle: "), `${p} frontmatter present`);
  check(body.includes("```json"), `${p} json fence present`);
  check(r.headers.get("x-markdown-tokens") && r.headers.get("x-original-tokens"), `${p} token headers`);
  check(r.headers.get("content-signal") === "ai-train=yes, search=yes, ai-input=yes", `${p} content-signal default`);
  check(r.headers.get("ETag") === null && r.headers.get("Last-Modified") === null, `${p} validators dropped`);
  check(Number(r.headers.get("Content-Length")) === Buffer.byteLength(body), `${p} byte length`);
}
// 2. plain passthrough byte-identical; Vary merged on HTML, assets untouched
{
  const r = await get("/treatments");
  const buf = Buffer.from(await r.arrayBuffer());
  check(buf.equals(readFileSync(join(ROOT, "treatments.html"))), "plain bytes identical");
  check(r.headers.get("x-markdown-tokens") === null, "plain has no token headers");
  check((r.headers.get("Vary") || "").toLowerCase().includes("accept"), "plain HTML carries Vary (cache correctness)");
  const css = await get("/styles.css", "text/markdown");
  check(css.headers.get("Vary") === null, "non-HTML asset gains no Vary");
}
// 3. Accept variants refuse correctly
{
  for (const a of ["text/markdown;q=0", "*/*", "text/html", "text/html, */*;q=0.8", undefined]) {
    const r = await get("/treatments", a);
    check(r.headers.get("Content-Type") === "text/html", `refuse ${a}`);
  }
  const r = await get("/treatments", "TEXT/MARKDOWN; charset=utf-8");
  check((r.headers.get("Content-Type") || "").startsWith("text/markdown"), "case+params accept");
}
// 4. content checks: EN + HI
{
  const t = await (await get("/treatments", "text/markdown")).text();
  check(t.includes("### What is PCNL surgery for kidney stones?"), "treatments faq heading");
  check(t.includes("https://wa.me/919818442016?text="), "content links kept absolute");
  check(!t.includes("](/credentials)") && !t.includes("](/experience)"), "nav links stripped, not leaked");
  check(!t.includes("Toggle mobile menu") && !t.includes("maps.google.com"), "chrome stripped");
  check(!/<[a-zA-Z\/!][^>]*>/.test(t), "no tags leak");
  const hi = await (await get("/hi/", "text/markdown")).text();
  check(hi.includes("डॉ. केशव अग्रवाल") && /[\u0900-\u097F]{10,}/.test(hi), "hindi intact");
  const idx = await (await get("/", "text/markdown")).text();
  check(idx.includes('title: "Urologist in Ghaziabad & Noida | Dr. Keshav Agarwal"'), "index title raw &");
}
// 5. 404 arm: markdown body, 404 status, no frontmatter, noindex backstop
{
  const r = await get("/nope", "text/markdown");
  const body = await r.text();
  check(r.status === 404, "md-404 keeps 404", r.status);
  check((r.headers.get("Content-Type") || "").startsWith("text/markdown"), "md-404 is markdown");
  check(!body.startsWith("---\n"), "md-404 omits frontmatter (no meta surface)");
  check(r.headers.get("X-Robots-Tag") === "noindex", "md-404 noindex backstop");
  const md200 = await get("/", "text/markdown");
  check(md200.headers.get("X-Robots-Tag") === null, "200 md has no noindex override");
}
// 6. assets + non-HTML bypass
{
  for (const p of ["/styles.css", "/banners.json", "/llms.txt", "/sitemap.xml"]) {
    const r = await get(p, "text/markdown");
    check(!(r.headers.get("Content-Type") || "").startsWith("text/markdown"), `${p} bypasses`);
  }
  const css = await get("/styles.css", "text/markdown");
  check(Buffer.from(await css.arrayBuffer()).equals(readFileSync(join(ROOT, "styles.css"))), "css bytes identical");
}
// 7. redirects, methods, HEAD, over-cap (bounded), exact boundary, ?v=
{
  const r = await get("/index.html", "text/markdown");
  check(r.status === 301 && r.headers.get("Location") === "/", "301 passthrough");
  const post = await get("/treatments", "text/markdown", { method: "POST" });
  check(post.headers.get("Content-Type") === "text/html", "POST passthrough");
  const head = await get("/treatments", "text/markdown", { method: "HEAD" });
  const headLen = Number(head.headers.get("Content-Length"));
  const getLen = Number((await get("/treatments", "text/markdown")).headers.get("Content-Length"));
  check(headLen === getLen && headLen > 0, "HEAD GET-equivalent length");
  check((await head.arrayBuffer()).byteLength === 0, "HEAD empty body");
  const big = await get("/big.html", "text/markdown");
  const bigBody = Buffer.from(await big.arrayBuffer());
  check(big.headers.get("Content-Type") === "text/html" && bigBody.length === 2097153, "over-cap full-HTML fallback");
  const exact = await get("/exact.html", "text/markdown");
  check((exact.headers.get("Content-Type") || "").startsWith("text/markdown"), "exactly-2MB boundary converts");
  const ver = await get("/treatments.html?v=2026072001", "text/markdown");
  check((ver.headers.get("Content-Type") || "").startsWith("text/markdown"), "?v= HTML still converts");
  const ranged = await get("/treatments", "text/markdown", { headers: { Range: "bytes=0-99" } });
  check((ranged.headers.get("Content-Type") || "") === "text/html", "Range arm passthrough untouched");
  check(Buffer.from(await ranged.arrayBuffer()).equals(readFileSync(join(ROOT, "treatments.html"))), "Range bytes identical");
}
// 8. determinism: two identical requests, identical bytes + tokens
{
  const r1 = await get("/", "text/markdown");
  const r2 = await get("/", "text/markdown");
  const [a, b] = [await r1.text(), await r2.text()];
  check(a === b, "conversion deterministic");
  check(r1.headers.get("x-markdown-tokens") === r2.headers.get("x-markdown-tokens") &&
    r1.headers.get("x-original-tokens") === r2.headers.get("x-original-tokens"),
    "token headers deterministic");
}
// 9. link safety: dangerous schemes degrade to text, brackets escaped
{
  const bad = await (await get("/badlinks.html", "text/markdown")).text();
  check(!bad.includes("javascript:"), "no javascript: link emitted");
  check(!bad.includes("JaVaScRiPt:"), "no mixed-case scheme emitted");
  check(!bad.includes("data:text/html") && !bad.includes("vbscript:"), "no data:/vbscript: emitted");
  check(bad.includes("click") && !bad.includes("](javascript"), "dangerous link degrades to text");
  check(bad.includes("sp") && bad.includes("tab"), "whitespace/tab scheme variants degrade to text");
  check(!/\(\s*"?\s*javascript/i.test(bad), "no normalized javascript: destination");
  check(bad.includes("[good](https://uro-care.com/fine)"), "allowlisted https link kept");
  check(bad.includes("a\\]\\(http://evil\\)"), "link-text brackets escaped");
  check(bad.includes("[paren](https://uro-care.com/x_%28y%29)"), "paren destination percent-encoded");
  const ent = await (await get("/entity.html", "text/markdown")).text();
  check(ent.includes('title: "A &copy; B &nbsp; C & D"'), "exotic entities literal, &amp; decoded");
}
// 10. origin headers: custom content-signal + Vary merge preserved
{
  const r = await get("/vary.html", "text/markdown");
  check(r.headers.get("content-signal") === "ai-train=no", "origin content-signal preserved (no default overwrite)");
  const vary = (r.headers.get("Vary") || "").split(",").map((v) => v.trim().toLowerCase());
  check(vary.includes("accept") && vary.includes("accept-language"), "origin Vary dims preserved + Accept merged");
  check(vary.filter((v) => v === "accept").length === 1, "Accept not duplicated");
}
// 11. failure edges: converter-throw fails open, ASSETS-throw propagates,
//     concurrent mixed requests stay isolated
{
  const RealTE = globalThis.TextEncoder;
  globalThis.TextEncoder = class { encode() { throw new Error("encoder down (injected)"); } };
  let threw = null;
  let fallback = null;
  try {
    fallback = await get("/treatments", "text/markdown");
  } catch (e) { threw = e; }
  globalThis.TextEncoder = RealTE;
  check(threw === null, "converter throw does not propagate");
  check(fallback !== null && fallback.headers.get("Content-Type") === "text/html", "converter throw fails open to HTML");
  check(Buffer.from(await fallback.arrayBuffer()).equals(readFileSync(join(ROOT, "treatments.html"))), "fail-open bytes identical");
  let flapThrew = false;
  try { await get("/flap.html", "text/markdown"); } catch { flapThrew = true; }
  check(flapThrew, "ASSETS-throw propagates (no original to return)");
  const [m1, p1, n1, c1, h1] = await Promise.all([
    get("/", "text/markdown"), get("/treatments"), get("/nope", "text/markdown"),
    get("/styles.css", "text/markdown"), get("/privacy", "text/markdown", { method: "HEAD" }),
  ]);
  check(m1.headers.get("Content-Type").startsWith("text/markdown")
    && p1.headers.get("Content-Type") === "text/html"
    && n1.status === 404 && c1.headers.get("Content-Type") === "text/css"
    && (await h1.arrayBuffer()).byteLength === 0, "concurrent mixed isolation");
  const qg = await get("/treatments", "text/markdown; q=0 garbage");
  check(qg.headers.get("Content-Type") === "text/html", "malformed q refuses (fail-safe HTML)");
}
// 12. secrecy at ASSETS layer
for (const p of ["/worker.js", "/wrangler.jsonc", "/tests/seo_verify.py"])
  check((await get(p, "text/markdown")).status === 404, `${p} -> 404`);

console.log(`\nmarkdown_pipeline: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
